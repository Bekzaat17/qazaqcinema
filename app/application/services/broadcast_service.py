"""Рассылки и уведомления.

Единая точка «кому и что рассылать»: собирает аудиторию (opted-in юзеры), строит
`BroadcastMessage` и ставит его в `BroadcastQueue` (worker разошлёт, соблюдая лимиты
Telegram). Сервисы-триггеры (ingest → новинка, бот-команда `/broadcast`) зовут этот
сервис, а не очередь напрямую — контент и аудитория считаются в одном месте.

Зависит только от портов (`BroadcastQueue`, `UserRepository`, `PosterStorage`) + URL
Web App (для кнопки).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.application.ports.broadcast import BroadcastMessage, BroadcastQueue
from app.application.ports.repositories import UserRepository
from app.application.ports.storage import PosterStorage
from app.domain.entities.movie import Movie
from app.domain.subscription.weekly import week_start

_NEW_MOVIE_INTRO = "🎬 Жаңа фильм қосылды!"
# Два письма в неделю про недельный выбор — и ни одним больше. Открытие окна и его
# закрытие: первое зовёт выбрать, второе подбирает забывших. Всё, что между, человек
# видит в самом приложении, и лишнее письмо тут стоило бы дороже пропущенного.
_WEEK_OPEN = (
    "🎟 Жаңа апта — жаңа таңдау!\n\n"
    "Кез келген фильмді таңдап, апта соңына дейін тегін көріңіз."
)
# «Жексенбіде», а не «ертең»: письмо уходит в субботу, и «завтра» человек прочитает
# вечером как «уже сегодня». Названный день недели однозначен в любой момент суток.
_WEEK_CLOSING = (
    "⏳ Апталық таңдауыңыз жексенбіде жабылады.\n\n"
    "Әлі алған жоқсыз — бір фильмді таңдап, тегін көріп үлгеріңіз."
)
_WATCH_BUTTON = "🍿 Көру"
_OPEN_BUTTON = "🍿 Кинотеатрды ашу"
# Запас под лимит подписи фото в Telegram (1024 симв.): длинное описание подрежем.
_CAPTION_LIMIT = 900
# Шаг назад по календарю — чтобы взять ключ прошлой недели, не считая его вручную.
_A_WEEK = timedelta(days=7)


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


class BroadcastService:
    def __init__(
        self,
        queue: BroadcastQueue,
        users: UserRepository,
        posters: PosterStorage,
        webapp_url: str,
    ) -> None:
        self._queue = queue
        self._users = users
        self._posters = posters
        self._webapp_url = webapp_url

    def _new_movie_message(self, movie: Movie) -> BroadcastMessage:
        """Письмо о новинке: постер ФАЙЛОМ С ДИСКА + текст + кнопка Web App.

        Именно файлом, а не ссылкой (см. `BroadcastMessage.photo_path`). Файла на диске
        нет → `local_path` вернёт None, письмо уйдёт текстом (не ошибка).
        """
        title = f"«{movie.title_kk}»"
        if movie.year is not None:
            title += f" ({movie.year})"
        text = _clip(f"{_NEW_MOVIE_INTRO}\n\n{title}\n\n{movie.description}", _CAPTION_LIMIT)
        button_url = self._webapp_url or None
        return BroadcastMessage(
            text=text,
            photo_path=self._posters.local_path(movie.poster_url),
            button_text=_WATCH_BUTTON if button_url else None,
            button_url=button_url,
        )

    async def notify_new_movie(self, movie: Movie) -> int:
        """Поставить рассылку о новинке всем opted-in. Вернуть число адресатов.

        Идемпотентность на уровне вызова: `ingest` зовёт это один раз на фильм и к этому
        моменту уже сбросил кэш каталога → клик из уведомления покажет новинку.
        """
        audience = await self._users.list_notifiable()
        return await self._queue.enqueue(self._new_movie_message(movie), audience)

    async def broadcast_custom(self, text: str) -> int:
        """Ручная рассылка админа (`/broadcast`): произвольный текст всем opted-in."""
        button_url = self._webapp_url or None
        message = BroadcastMessage(
            text=_clip(text, 4096),
            button_text=_OPEN_BUTTON if button_url else None,
            button_url=button_url,
        )
        audience = await self._users.list_notifiable()
        return await self._queue.enqueue(message, audience)

    def _open_app_message(self, text: str) -> BroadcastMessage:
        """Письмо без картинки, с кнопкой в приложение: выбор делается только там."""
        button_url = self._webapp_url or None
        return BroadcastMessage(
            text=text,
            button_text=_OPEN_BUTTON if button_url else None,
            button_url=button_url,
        )

    async def notify_weekly_pick_open(self, now: datetime) -> int:
        """Понедельник: окно открылось. Пишем тем, кто брал фильм на ПРОШЛОЙ неделе.

        Аудитория узкая намеренно: человек уже один раз выбрал — значит механика ему
        нужна. Рассылать всей базе значило бы еженедельно дёргать людей, которым это
        неинтересно, и первым же письмом выучить их выключать уведомления.
        """
        previous = week_start(now - _A_WEEK)
        audience = await self._users.list_weekly_pickers(previous, now)
        if not audience:
            return 0
        return await self._queue.enqueue(self._open_app_message(_WEEK_OPEN), audience)

    async def notify_weekly_pick_closing(self, now: datetime) -> int:
        """Суббота: окно скоро закроется. Пишем тем, кто на этой неделе выбор не потратил.

        Это же лечит единственную слабость общего окна: взявший фильм в воскресенье вечером
        получает вечер, а не неделю. Напоминание разводит поток по неделе — и подбирает тех,
        кто просто забыл.
        """
        audience = await self._users.list_weekly_idle(week_start(now), now)
        if not audience:
            return 0
        return await self._queue.enqueue(self._open_app_message(_WEEK_CLOSING), audience)

    async def set_user_notifications(self, telegram_id: int, enabled: bool) -> None:
        """Тумблер в профиле Web App: включить/выключить рассылки для юзера."""
        await self._users.set_notifications(telegram_id, enabled)
