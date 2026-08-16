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

from app.application.ports.lock import Lock
from app.application.ports.repositories import (
    MovieRepository,
    UserEventRepository,
    UserRepository,
    VideoDeliveryRepository,
)
from app.application.ports.telegram import RecipientUnreachableError, TelegramNotifier
from app.domain.analytics.events import EventKind
from app.domain.entities.user import User


class PlaybackOutcome(Enum):
    DELIVERED = auto()       # видео отправлено в личку (protect_content)
    GIFT_DELIVERED = auto()  # то же, но за счёт подарочного первого фильма
    NO_ACCESS = auto()       # ни подписки, ни подарка → фронт показывает пэйволл
    NOT_FOUND = auto()       # фильма с таким id нет
    BOT_BLOCKED = auto()     # получатель не открыл чат с ботом → фронт просит открыть бота


class _Gift(Enum):
    """На каком основании отдаём видео — внутреннее решение гейта, наружу не торчит.

    Четыре состояния вместо булева «бесплатно ли»: откат права при сорванной доставке
    касается ТОЛЬКО CLAIMED (право забрали сейчас). У REPEAT откатывать нечего — подарок
    потрачен давно, а сброс стёр бы его насовсем.
    """

    NONE = auto()     # по активной подписке
    CLAIMED = auto()  # право на подарок забрали прямо сейчас
    REPEAT = auto()   # повтор уже подаренного фильма
    DENIED = auto()   # ни подписки, ни подарка → пэйволл


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
    ) -> None:
        self._movies = movies
        self._notifier = notifier
        self._lock = lock
        self._deliveries = deliveries
        self._events = events
        self._users = users

    async def deliver(
        self, user: User, movie_id: int, now: datetime, *, use_free_view: bool = False
    ) -> PlaybackOutcome:
        """Отдать видео: по подписке либо за счёт подарочного первого фильма.

        `use_free_view` — ЯВНОЕ согласие потратить подарок (юзер нажал «Тегін көру» в
        модалке). Без флага подарок не тратится: иначе он сгорал бы молча, например от
        deep-link `?startapp=m_42`, где человек и не думал его расходовать.
        """
        # Доступ проверяем ПЕРВЫМ: без права на просмотр даже не раскрываем, есть ли фильм.
        gift = await self._resolve_gift(user, movie_id, now, use_free_view)
        if gift is _Gift.DENIED:
            # Упор в стену — ключевой шаг воронки: столько людей увидели пэйволл, имея
            # желание смотреть. Пишем здесь, а не на фронте: отдельная ручка ради счётчика
            # не нужна, а этот код и есть точная точка отказа.
            await self._events.add(user.telegram_id, EventKind.PAYWALL, meta=str(movie_id))
            return PlaybackOutcome.NO_ACCESS
        movie = await self._movies.get(movie_id)
        if movie is None:
            if gift is _Gift.CLAIMED:
                # Забрали право под несуществующий фильм — возвращаем, подарок не потрачен.
                await self._users.release_free_view(user.telegram_id, movie_id)
            return PlaybackOutcome.NOT_FOUND
        # Анти-двойной-клик: на плохом инете юзер жмёт «Көру» много раз. Лок на
        # несколько секунд → одна отправка; повтор в окне — тихий no-op, но всё равно
        # DELIVERED, чтобы фронт показал ту же модалку «видео отправлено», а не ошибку.
        lock_key = f"send_video:{user.telegram_id}:{movie_id}"
        if not await self._lock.acquire(lock_key, self._SEND_LOCK_TTL):
            # Право на подарок тут НЕ возвращаем: оно потрачено на ту самую отправку,
            # которую делает опередивший нас запрос.
            return (
                PlaybackOutcome.DELIVERED
                if gift is _Gift.NONE
                else PlaybackOutcome.GIFT_DELIVERED
            )
        try:
            message_id = await self._notifier.send_protected_video(
                user.telegram_id, movie.telegram_file_id, caption=movie.title_kk
            )
        except RecipientUnreachableError:
            # Юзер открыл Mini App, но не начал чат с ботом. Лок (TTL ~3 c) не снимаем:
            # окно мало, а доступ к боту юзер чинит дольше → ложного «доставлено» не будет.
            if gift is _Gift.CLAIMED:
                # А вот подарок вернуть ОБЯЗАНЫ: человек его не увидел. Иначе он чинит
                # доступ к боту, возвращается — и упирается в пэйволл, так и не поняв,
                # что ему вообще дарили.
                await self._users.release_free_view(user.telegram_id, movie_id)
            return PlaybackOutcome.BOT_BLOCKED
        # Запоминаем выдачу (chat=личка юзера) → удалим это сообщение, когда подписка
        # истечёт (`SubscriptionService.expire_due`): оплаченное видео не остаётся навсегда.
        await self._deliveries.add(user.telegram_id, user.telegram_id, message_id)
        # Считаем просмотр только на реальной доставке (Фаза 13): повтор-в-окне не дошёл
        # сюда (лок вернул DELIVERED раньше) → двойной клик не накручивает счётчик.
        await self._movies.increment_play_count(movie_id)
        # Просмотр в истории юзера (кто и что смотрел) — там же, где счётчик фильма:
        # повтор-в-окне сюда не доходит, значит двойной клик не задваивает и событие.
        # Подарочный просмотр пишем ОТДЕЛЬНЫМ видом, а не вдобавок к `play`: смешав их,
        # мы потеряли бы ровно ту цифру, ради которой затевалась воронка, — сколько людей
        # попробовали продукт бесплатно.
        if gift is _Gift.NONE:
            await self._events.add(user.telegram_id, EventKind.PLAY, meta=str(movie_id))
            return PlaybackOutcome.DELIVERED
        await self._events.add(user.telegram_id, EventKind.FREE_PLAY, meta=str(movie_id))
        return PlaybackOutcome.GIFT_DELIVERED

    async def _resolve_gift(
        self, user: User, movie_id: int, now: datetime, use_free_view: bool
    ) -> _Gift:
        """Решить, на каком основании отдаём видео. Единственное место с правилом доступа.

        Порядок ветвей важен: подписка сначала — у подписчика подарок не тратится, он ему
        не нужен и пригодится, если подписка когда-нибудь кончится.
        """
        if user.has_active_access(now):
            return _Gift.NONE
        if user.is_gifted_movie(movie_id):
            # Уже подаренный фильм: право потрачено раньше, тратить нечего. Отдаём снова —
            # его видео мы сами сносим через ~40 ч (`VideoRetentionService`).
            return _Gift.REPEAT
        if not (use_free_view and user.can_use_free_view()):
            return _Gift.DENIED
        # Право забираем ДО отправки: захват атомарен, а сорванную доставку мы откатим.
        # Обратный порядок («сначала отправить, потом пометить») на двойном тапе успел бы
        # отправить два разных фильма бесплатно.
        if await self._users.claim_free_view(user.telegram_id, movie_id, now):
            return _Gift.CLAIMED
        # Захват не удался — значит между загрузкой `user` и этой строкой право уже ушло.
        # Перечитываем: если подарен ИМЕННО этот фильм (нас опередил наш же второй тап),
        # это повтор, а не отказ. Без перечитывания человек, которому подарок ровно сейчас
        # выдали, увидел бы на второй тап пэйволл — и этот же ложный отказ попал бы в
        # метрику воронки.
        fresh = await self._users.get(user.telegram_id)
        if fresh is not None and fresh.is_gifted_movie(movie_id):
            return _Gift.REPEAT
        return _Gift.DENIED
