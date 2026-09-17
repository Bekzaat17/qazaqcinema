"""DTO результата авторизации Web App."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.domain.entities.user import User
from app.domain.subscription.weekly import week_end


class AuthOut(BaseModel):
    telegram_id: int
    status: str
    expires_at: datetime | None = None
    has_access: bool
    # Сессионный токен: клиент кладёт его в localStorage и шлёт в Authorization
    # вместо initData. None — Redis недоступен, клиент остаётся на initData (fail-open).
    token: str | None = None
    # Начальное состояние тумблера рассылок — фронт рисует профиль без доп. запроса.
    notifications_enabled: bool = True
    # Недельный бесплатный выбор. Фронт по этим полям решает, что показать вместо
    # пэйволла: приглашение «возьми фильм на неделю» (выбор свободен), бейдж «Менің
    # таңдауым» на своём фильме и счётчик до конца окна. `week_ends_at` ОДИН на всех —
    # окно общее (понедельник 00:00 по Алматы), считать остаток по каждому не нужно.
    # Поля приходят и из `GET /api/me`: состояние меняется на сервере (в том числе само,
    # сменой недели) и должно доезжать без перезахода.
    weekly_pick_available: bool = True
    weekly_movie_id: int | None = None
    week_ends_at: datetime | None = None
    # Фильм, подаренный ПРОШЛОЙ, одноразовой механикой: он бесплатен навсегда, и бейдж на
    # нём фронт рисует по-прежнему. Поля «подарок ещё цел» тут больше нет намеренно —
    # забрать его нельзя, и оставить флаг значило бы рисовать кнопку в никуда.
    free_view_movie_id: int | None = None
    # @-имя публичного канала без «@» — фронту нужно, чтобы шторка гейта вела в канал.
    # Отдаём с бэка, а не собственной VITE-переменной: канал уже описан в конфиге бэкенда
    # (`BOT_PUBLIC_CHANNEL_USERNAME`), и вторая копия того же имени однажды разъедется —
    # причём молча, ссылкой в никуда ровно у тех, кого мы просим подписаться.
    channel_username: str = ""
    # Открыт ли чат с ботом. Видео уходит ТОЛЬКО туда, а написать первым бот не вправе —
    # значит для зашедшего по ссылке (из браузера/поиска) «Көру» физически не сработает.
    # Фронт по этому полю зовёт в бота ЗАРАНЕЕ, вместо ошибки после потраченного подарка.
    bot_started: bool = True

    @classmethod
    def from_domain(
        cls, user: User, now: datetime, token: str | None = None, channel_username: str = ""
    ) -> AuthOut:
        # `weekly_movie_id` отдаём ТОЛЬКО пока он про ТЕКУЩУЮ неделю: в колонке лежит и
        # позапрошлый выбор, а бейдж «Менің таңдауым» на фильме, право на который уже
        # истекло, обещал бы человеку доступ, которого нет.
        picked_this_week = not user.can_pick_weekly(now)
        return cls(
            telegram_id=user.telegram_id,
            status=user.status.value,
            expires_at=user.expires_at,
            has_access=user.has_active_access(now),
            token=token,
            notifications_enabled=user.notifications_enabled,
            weekly_pick_available=not picked_this_week,
            weekly_movie_id=user.weekly_movie_id if picked_this_week else None,
            week_ends_at=week_end(now),
            free_view_movie_id=user.free_view_movie_id,
            channel_username=channel_username,
            bot_started=user.has_bot_chat(),
        )
