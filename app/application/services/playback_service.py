"""Use-case «отдать видео подписчику» с защитой контента.

Гейт доступа — единый источник правды `User.has_active_access`. Видео НИКОГДА не
уходит без активной подписки. Отправка — через порт `TelegramNotifier`
(`send_protected_video` → `bot.send_video(protect_content=True)`), `telegram_file_id`
наружу (в API-DTO) не отдаётся — его видит только бот.

Почему не inline: `InlineQueryResult*` не поддерживают `protect_content` (проверено на
aiogram 3.x), поэтому защищённую выдачу делает бот напрямую в личку, а триггерит её
API-эндпоинт `/play` (initData-гейт) или, в будущем, deep-link.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum, auto

from app.application.ports.channel import ChannelMembership
from app.application.ports.lock import Lock
from app.application.ports.repositories import (
    MovieRepository,
    UserEventRepository,
    UserRepository,
    VideoDeliveryRepository,
)
from app.application.ports.telegram import (
    RecipientUnreachableError,
    TelegramNotifier,
    TelegramTemporarilyUnavailableError,
)
from app.application.services.daily_service import DailyMovieService
from app.domain.analytics.events import EventKind
from app.domain.entities.user import User
from app.domain.subscription.weekly import week_start


class PlaybackOutcome(Enum):
    DELIVERED = auto()       # видео отправлено в личку (protect_content)
    GIFT_DELIVERED = auto()  # то же, но за счёт подарочного первого фильма
    DAILY_DELIVERED = auto() # то же, но это бесплатный фильм дня (подарок цел)
    NO_ACCESS = auto()       # ни подписки, ни бесплатного права → фронт показывает пэйволл
    # Хочет взять фильм на неделю, но не подписан на канал. Отдельно от NO_ACCESS: это
    # не стена, а одно действие до цели, и показать тут пэйволл значило бы продавать
    # человеку то, что он может получить бесплатно прямо сейчас.
    NEED_CHANNEL = auto()
    NOT_FOUND = auto()       # фильма с таким id нет
    BOT_BLOCKED = auto()     # получатель не открыл чат с ботом → фронт просит открыть бота
    # Telegram не принял отправку СЕЙЧАС (флуд-лимит на всплеске, сеть, 5xx). Отдельно от
    # BOT_BLOCKED: там виноват закрытый чат и человек идёт его открывать, здесь виноват
    # момент и надо просто повторить (на фронт это не должно уходить как 500).
    TRY_LATER = auto()


class _Gift(Enum):
    """На каком основании отдаём видео — внутреннее решение гейта, наружу не торчит.

    Состояния, а не булево «бесплатно ли»: откат при сорванной доставке касается ТОЛЬКО
    `WEEKLY_CLAIMED` (право забрали прямо сейчас). У `WEEKLY` и `LEGACY_GIFT` откатывать
    нечего — там право уже было, и сброс отнял бы его ни за что.
    """

    NONE = auto()            # по активной подписке
    DAILY = auto()           # фильм дня — сегодня бесплатен всем, тратить нечего
    WEEKLY = auto()          # свой недельный фильм: пересмотр внутри той же недели
    WEEKLY_CLAIMED = auto()  # недельный выбор забрали прямо сейчас
    # Одноразовый подарок прошлой механики. Новым НЕ выдаётся (захвата больше нет), но у
    # потративших остаётся навсегда: отнимать у человека то, что он уже держит, не за что.
    # Множество таких людей не растёт и со временем само уходит в ноль.
    LEGACY_GIFT = auto()
    NEEDS_CHANNEL = auto()   # хочет взять на неделю, но не подписан на канал
    DENIED = auto()          # смотреть не на что → пэйволл


# Основание выдачи → что записать в журнал и что ответить фронту. Таблицами, а не
# цепочкой if-ов: оснований стало четыре, и в двух местах (ветка занятого лока и успешная
# отправка) они обязаны отображаться ОДИНАКОВО — разъедься эти места, и повтор-в-окне
# отвечал бы не тем, чем первая отправка.
_EVENT_FOR: dict[_Gift, EventKind] = {
    _Gift.NONE: EventKind.PLAY,
    _Gift.DAILY: EventKind.DAILY_PLAY,
    _Gift.WEEKLY: EventKind.WEEKLY_PLAY,
    _Gift.WEEKLY_CLAIMED: EventKind.WEEKLY_PLAY,
    _Gift.LEGACY_GIFT: EventKind.FREE_PLAY,
}

_OUTCOME_FOR: dict[_Gift, PlaybackOutcome] = {
    _Gift.NONE: PlaybackOutcome.DELIVERED,
    _Gift.DAILY: PlaybackOutcome.DAILY_DELIVERED,
    _Gift.WEEKLY: PlaybackOutcome.GIFT_DELIVERED,
    _Gift.WEEKLY_CLAIMED: PlaybackOutcome.GIFT_DELIVERED,
    _Gift.LEGACY_GIFT: PlaybackOutcome.GIFT_DELIVERED,
}


def _outcome_for(gift: _Gift) -> PlaybackOutcome:
    return _OUTCOME_FOR[gift]


class PlaybackService:
    # TTL лока отправки: столько секунд повторные /play той же пары юзер+фильм — no-op.
    _SEND_LOCK_TTL = 3

    def __init__(
        self,
        movies: MovieRepository,
        notifier: TelegramNotifier,
        lock: Lock,
        deliveries: VideoDeliveryRepository,
        events: UserEventRepository,
        users: UserRepository,
        daily: DailyMovieService,
        membership: ChannelMembership,
    ) -> None:
        self._movies = movies
        self._notifier = notifier
        self._lock = lock
        self._deliveries = deliveries
        self._events = events
        self._users = users
        self._daily = daily
        self._membership = membership

    async def deliver(
        self, user: User, movie_id: int, now: datetime, *, use_weekly_pick: bool = False
    ) -> PlaybackOutcome:
        """Отдать видео: по подписке, как фильм дня, недельный выбор либо старый подарок.

        `use_weekly_pick` — ЯВНОЕ согласие потратить недельный выбор (юзер подтвердил в
        шторке). Без флага выбор не тратится: иначе он сгорал бы молча, например от
        deep-link `?startapp=m_42`, где человек и не думал его расходовать. Фильму дня и
        пересмотру своего недельного флаг не нужен — там тратить нечего.
        """
        # Доступ проверяем ПЕРВЫМ: без права на просмотр даже не раскрываем, есть ли фильм.
        gift = await self._resolve_gift(user, movie_id, now, use_weekly_pick)
        if gift is _Gift.NEEDS_CHANNEL:
            # Знаменатель всей затеи: сколько людей увидели требование подписки. Без него
            # прирост канала не отличить от органического.
            await self._events.add(user.telegram_id, EventKind.CHANNEL_GATE, meta=str(movie_id))
            return PlaybackOutcome.NEED_CHANNEL
        if gift is _Gift.DENIED:
            # Упор в стену — ключевой шаг воронки: столько людей увидели пэйволл, имея
            # желание смотреть. Пишем здесь, а не на фронте: отдельная ручка ради счётчика
            # не нужна, а этот код и есть точная точка отказа.
            await self._events.add(user.telegram_id, EventKind.PAYWALL, meta=str(movie_id))
            return PlaybackOutcome.NO_ACCESS
        movie = await self._movies.get(movie_id)
        if movie is None:
            # Забрали право под несуществующий фильм — возвращаем, неделя не потрачена.
            await self._rollback(gift, user, movie_id, now)
            return PlaybackOutcome.NOT_FOUND
        # Анти-двойной-клик: на плохом инете юзер жмёт «Көру» много раз. Лок на
        # несколько секунд → одна отправка; повтор в окне — тихий no-op, но всё равно
        # DELIVERED, чтобы фронт показал ту же модалку «видео отправлено», а не ошибку.
        lock_key = f"send_video:{user.telegram_id}:{movie_id}"
        if not await self._lock.acquire(lock_key, self._SEND_LOCK_TTL):
            if gift is _Gift.WEEKLY_CLAIMED:
                # Занятый лок при СВЕЖЕМ захвате — это НЕ «нас опередили с отправкой».
                # Захват атомарен: выигрывает ровно один запрос, и держатель лока наш
                # выбор не забирал. Значит он уже сорвался и вернул право (единственный
                # путь, которым оно снова стало свободным) — а мы его перезабрали.
                # Сорваться, не сняв лок, можно только на недоступном получателе, поэтому
                # и ответ тот же: пусть человек откроет чат с ботом. Считать это доставкой
                # нельзя — видео не отправит никто, неделя сгорит молча, и человек упрётся
                # в пэйволл, так и не увидев фильма, который уже выбрал.
                await self._rollback(gift, user, movie_id, now)
                return PlaybackOutcome.BOT_BLOCKED
            # У подписки, фильма дня и пересмотра отправку действительно делает опередивший
            # запрос, а тратить там нечего — отвечаем как он, чтобы фронт показал ту же
            # модалку «видео отправлено», а не ошибку.
            return _outcome_for(gift)
        try:
            message_id = await self._notifier.send_protected_video(
                user.telegram_id, movie.telegram_file_id, caption=movie.title_kk
            )
        except RecipientUnreachableError:
            # Юзер открыл Mini App, но не начал чат с ботом. Лок (TTL ~3 c) не снимаем:
            # окно мало, а доступ к боту юзер чинит дольше → ложного «доставлено» не будет.
            # Снимаем сам факт открытого чата: раз бот не смог написать, чата фактически
            # нет (не нажимал /start или заблокировал) — и фронт покажет «Ботты ашу»
            # ДО следующей попытки, а не после неё. Обратно факт вернёт /start.
            await self._users.set_bot_started(user.telegram_id, None)
            # А вот выбор вернуть ОБЯЗАНЫ: человек фильма не увидел. Иначе он чинит доступ
            # к боту, возвращается — и упирается в пэйволл, потеряв неделю ни за что.
            await self._rollback(gift, user, movie_id, now)
            return PlaybackOutcome.BOT_BLOCKED
        except TelegramTemporarilyUnavailableError:
            # Флуд-лимит/сеть/5xx: чат в порядке, виноват момент. Флаг чата НЕ снимаем —
            # иначе всплеск трафика из канала массово помечал бы исправных людей как
            # «бота не открыл» и гнал их в чат без причины.
            # Выбор возвращаем по той же причине, что и выше: человек фильма не увидел.
            await self._rollback(gift, user, movie_id, now)
            return PlaybackOutcome.TRY_LATER
        # Отправка удалась — значит чат с ботом существует, что бы ни было записано в
        # флаге. Чинит устаревший NULL: у людей, начавших чат до появления колонки (или
        # снятых прошлой неудачной отправкой), иначе навсегда висела бы шторка «Ботты
        # ашу» при живом чате — а нажать в нём было бы нечего.
        if not user.has_bot_chat():
            await self._users.set_bot_started(user.telegram_id, now)
        # Запоминаем выдачу (chat=личка юзера) → удалим это сообщение, когда подписка
        # истечёт (`SubscriptionService.expire_due`): оплаченное видео не остаётся навсегда.
        await self._deliveries.add(user.telegram_id, user.telegram_id, message_id)
        # Считаем просмотр только на реальной доставке: повтор-в-окне не дошёл
        # сюда (лок вернул DELIVERED раньше) → двойной клик не накручивает счётчик.
        await self._movies.increment_play_count(movie_id)
        # Просмотр в истории юзера (кто и что смотрел) — там же, где счётчик фильма:
        # повтор-в-окне сюда не доходит, значит двойной клик не задваивает и событие.
        # Каждое основание пишем СВОИМ видом (`_EVENT_FOR`), а не всё как `play`: подарок
        # меряет «попробовал продукт», фильм дня — возвраты, подписка — оплаченный спрос.
        # Смешай их — и не останется ни одной из трёх цифр.
        await self._events.add(user.telegram_id, _EVENT_FOR[gift], meta=str(movie_id))
        if gift is _Gift.WEEKLY_CLAIMED:
            # Вторым событием, а не вместо просмотра: человек и выбрал, и посмотрел. Слей
            # их — и «сколько людей взяли фильм» утонет в пересмотрах за ту же неделю.
            # Пишем ЗДЕСЬ, после удавшейся доставки, а не в момент захвата: захват
            # откатывается (см. `_rollback`), и откаченный выбор не должен попасть в счёт.
            await self._events.add(user.telegram_id, EventKind.WEEKLY_PICK, meta=str(movie_id))
        return _outcome_for(gift)

    async def _rollback(self, gift: _Gift, user: User, movie_id: int, now: datetime) -> None:
        """Вернуть недельный выбор, если видео так и не ушло.

        Одна точка на все три ветки срыва (нет фильма, чат закрыт, Telegram занят): пока
        откат был скопирован по месту, любая новая ветка норовила его забыть — и человек
        терял неделю, не увидев фильма. Откатывать можно ТОЛЬКО свежий захват: у
        пересмотра и старого подарка право было и до нас.
        """
        if gift is _Gift.WEEKLY_CLAIMED:
            await self._users.release_weekly_pick(user.telegram_id, movie_id, week_start(now))

    async def _resolve_gift(
        self, user: User, movie_id: int, now: datetime, use_weekly_pick: bool
    ) -> _Gift:
        """Решить, на каком основании отдаём видео. Единственное место с правилом доступа.

        Порядок ветвей важен и читается сверху вниз как «самое дешёвое для нас — первым»:
        у подписчика недельный выбор НЕ тратится (он ему не нужен и пригодится, если
        подписка кончится), а бесплатное отдаётся раньше, чем что-либо расходуется.
        """
        if user.has_active_access(now):
            return _Gift.NONE
        if await self._daily.today_id(now) == movie_id:
            # Фильм дня: сегодня он открыт всем, и недельный выбор при этом НЕ тратится —
            # иначе человек лишался бы права выбрать СВОЁ кино, просто нажав на витрину.
            return _Gift.DAILY
        if user.is_weekly_movie(movie_id, now):
            # Свой фильм этой недели: право уже потрачено, тратить нечего. Отдаём снова —
            # видео мы сами сносим через ~40 ч (`VideoRetentionService`), а право живёт до
            # понедельника, и без этой ветки наша же уборка читалась бы как «дали и отняли».
            return _Gift.WEEKLY
        if user.is_gifted_movie(movie_id):
            # Наследство прошлой механики: фильм, подаренный когда-то одноразовым подарком.
            # Остаётся бесплатным навсегда — отнимать у человека то, что он уже держит, не
            # за что. Новым это состояние не выдаётся: захвата подарка больше нет.
            return _Gift.LEGACY_GIFT
        if not (use_weekly_pick and user.can_pick_weekly(now)):
            return _Gift.DENIED
        # Подписку спрашиваем ПОСЛЕДНЕЙ из проверок: это сетевой вызов к Telegram, и
        # дёргать его ради человека, который на этой неделе выбор уже потратил, незачем.
        if not await self._membership.is_member(user.telegram_id):
            return _Gift.NEEDS_CHANNEL
        # Право забираем ДО отправки: захват атомарен, а сорванную доставку мы откатим.
        # Обратный порядок («сначала отправить, потом пометить») на двойном тапе успел бы
        # отправить два разных фильма бесплатно.
        if await self._users.claim_weekly_pick(user.telegram_id, movie_id, week_start(now)):
            return _Gift.WEEKLY_CLAIMED
        # Захват не удался — значит между загрузкой `user` и этой строкой выбор уже ушёл.
        # Перечитываем: если ушёл ИМЕННО на этот фильм (нас опередил наш же второй тап),
        # это пересмотр, а не отказ. Без перечитывания человек, которому выбор ровно сейчас
        # засчитали, увидел бы на второй тап пэйволл — и этот ложный отказ попал бы в
        # метрику воронки.
        fresh = await self._users.get(user.telegram_id)
        if fresh is not None and fresh.is_weekly_movie(movie_id, now):
            return _Gift.WEEKLY
        return _Gift.DENIED
