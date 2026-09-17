"""Сущность «Пользователь» с доменной логикой проверки доступа."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.domain.entities.enums import UserStatus
from app.domain.subscription.weekly import week_start


@dataclass(slots=True)
class User:
    telegram_id: int
    username: str | None = None
    status: UserStatus = UserStatus.NEW
    expires_at: datetime | None = None
    selected_tariff: str | None = None
    notifications_enabled: bool = True  # рассылки о новинках; opt-out, по умолчанию ВКЛ
    # Открыт ли чат с ботом. Telegram не даёт боту написать первым, а всё видео уходит
    # именно в чат — значит без этого факта человек физически не может получить фильм,
    # хотя каталог в Mini App ему виден (зашёл по ссылке/из браузера, /start не нажимал).
    # Проставляется на /start, снимается на недоставке (бот заблокирован) — см. порт.
    bot_started_at: datetime | None = None
    # Подарочный первый фильм: человек должен увидеть продукт ДО пэйволла. Оба поля
    # проставляются один раз, атомарно (`UserRepository.claim_free_view`).
    free_view_used_at: datetime | None = None  # None → подарок ещё не потрачен
    free_view_movie_id: int | None = None      # какой фильм подарен (None у плативших-до-запуска)
    # Недельный бесплатный выбор: один фильм на ОБЩЕЕ для всех окно (понедельник 00:00 по
    # Алматы, см. `domain/subscription/weekly`). Храним не срок, а КЛЮЧ ОКНА — дату
    # понедельника: право освобождается сменой ключа, гасить его нечем и незачем.
    weekly_week: date | None = None      # на какую неделю взят фильм (None — не выбирал)
    weekly_movie_id: int | None = None   # какой именно
    # Telegram Premium — прокси платёжеспособности из initData. В доступе НЕ участвует
    # (`has_active_access` его не смотрит): это признак аудитории, а не право.
    is_premium: bool = False

    def has_active_access(self, now: datetime) -> bool:
        """Единственный источник правды о доступе (used: inline-выдача, API-гейт)."""
        return (
            self.status is UserStatus.ACTIVE
            and self.expires_at is not None
            and self.expires_at > now
        )

    def has_bot_chat(self) -> bool:
        """Может ли бот вообще прислать этому человеку видео (чат открыт и не заблокирован)."""
        return self.bot_started_at is not None

    def can_use_free_view(self) -> bool:
        """Подарок ещё не потрачен → человек вправе открыть ОДИН любой фильм бесплатно."""
        return self.free_view_used_at is None

    def can_pick_weekly(self, now: datetime) -> bool:
        """Выбор на ЭТУ неделю ещё свободен (не выбирал вовсе либо выбирал на прошлой)."""
        return self.weekly_week != week_start(now)

    def is_weekly_movie(self, movie_id: int, now: datetime) -> bool:
        """Его выбор на текущую неделю: пересматривать можно сколько угодно раз.

        Та же причина, что у `is_gifted_movie`: видео из чата мы сносим через ~40 ч
        (`VideoRetentionService`), а право живёт до конца недели — без этого правила наша
        же уборка выглядела бы как «дали и отняли» на третий день.
        """
        return self.weekly_movie_id == movie_id and self.weekly_week == week_start(now)

    def is_gifted_movie(self, movie_id: int) -> bool:
        """Этот фильм ему уже подарен → повторная выдача бесплатна и после чистки видео.

        Telegram-сообщение с видео мы сносим через ~40 ч (`VideoRetentionService`), и без
        этого правила человек терял бы подарок из-за нашей же уборки — выглядело бы как
        «дали и отняли». Бесплатен только ЭТОТ фильм: любой другой упирается в пэйволл.
        """
        return self.free_view_movie_id == movie_id
