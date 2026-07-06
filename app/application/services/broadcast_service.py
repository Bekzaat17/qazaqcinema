"""Рассылки и уведомления (Фаза 12).

Единая точка «кому и что рассылать»: собирает аудиторию (opted-in юзеры), строит
`BroadcastMessage` и ставит его в `BroadcastQueue` (worker разошлёт, соблюдая лимиты
Telegram). Сервисы-триггеры (ingest → новинка, бот-команда `/broadcast`) зовут этот
сервис, а не очередь напрямую — контент и аудитория считаются в одном месте.

Зависит только от портов (`BroadcastQueue`, `UserRepository`) + URL Web App (для кнопки).
"""

from __future__ import annotations

from urllib.parse import urljoin

from app.application.ports.broadcast import BroadcastMessage, BroadcastQueue
from app.application.ports.repositories import UserRepository
from app.domain.entities.movie import Movie

_NEW_MOVIE_INTRO = "🎬 Жаңа фильм қосылды!"
_WATCH_BUTTON = "🍿 Көру"
_OPEN_BUTTON = "🍿 Кинотеатрды ашу"
# Запас под лимит подписи фото в Telegram (1024 симв.): длинное описание подрежем.
_CAPTION_LIMIT = 900


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


class BroadcastService:
    def __init__(
        self, queue: BroadcastQueue, users: UserRepository, webapp_url: str
    ) -> None:
        self._queue = queue
        self._users = users
        self._webapp_url = webapp_url

    def _poster_public_url(self, poster_url: str) -> str | None:
        """Абсолютный URL постера для Telegram (тот сам качает картинку по URL).

        `poster_url` — относительный (`/posters/x.jpg`); склеиваем с origin Web App.
        Web App не сконфигурен (локаль) → None, шлём текстом.
        """
        if not self._webapp_url.startswith("http"):
            return None
        return urljoin(self._webapp_url, poster_url)

    def _new_movie_message(self, movie: Movie) -> BroadcastMessage:
        title = f"«{movie.title_kk}»"
        if movie.year is not None:
            title += f" ({movie.year})"
        text = _clip(f"{_NEW_MOVIE_INTRO}\n\n{title}\n\n{movie.description}", _CAPTION_LIMIT)
        button_url = self._webapp_url or None
        return BroadcastMessage(
            text=text,
            photo_url=self._poster_public_url(movie.poster_url),
            button_text=_WATCH_BUTTON if button_url else None,
            button_url=button_url,
        )

    async def notify_new_movie(self, movie: Movie) -> int:
        """Поставить рассылку о новинке всем opted-in. Вернуть число адресатов.

        Идемпотентность на уровне вызова: `ingest` зовёт это один раз на фильм (Фаза 11.2
        уже инвалидировала кэш каталога → клик из уведомления покажет новинку).
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

    async def set_user_notifications(self, telegram_id: int, enabled: bool) -> None:
        """Тумблер в профиле Web App: включить/выключить рассылки для юзера."""
        await self._users.set_notifications(telegram_id, enabled)
