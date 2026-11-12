"""Ежедневное личное напоминание редактору пополнить каталог."""

from __future__ import annotations

import logging
from datetime import datetime

from app.application.ports.lock import Lock
from app.application.ports.telegram import (
    RecipientUnreachableError,
    TelegramNotifier,
    TelegramTemporarilyUnavailableError,
)
from app.domain.catalog.daily import TZ

logger = logging.getLogger(__name__)

_MESSAGES = (
    "Алия, каталог бүгін де сізді күтіп отыр 😄 Кем дегенде бір видео қосайық! /add 🎬",
    "Алия, бір видео қоссаңыз, каталог та, көрермен де қуанады 😄 Бүгінгі миссия: /add 🎬",
    "Алия, каталог диета ұстап жүрген жоқ қой 😄 Кем дегенде бір видеомен тойдырайық! /add 🍿",
    "Алия, бүгінгі суперқабілетіңіз — бір видео жүктеп, біреудің күнін жақсарту 😄 /add 🎬",
    "Алия, бір видео ғана десек те, екеуіне ешкім ренжімейді 😄 Каталогты толықтырайық! /add 🍿",
    "Алия, көрермен попкорнын дайындап қойды 😄 Енді кем дегенде бір видео қосайық! /add 🎬",
    "Алия, каталог «жаңа видео бар ма?» деп сұрап жатыр 😄 Біреуін болса да қосайық! /add 🍿",
)


class ContentReminderService:
    def __init__(self, notifier: TelegramNotifier, lock: Lock, recipient_id: int) -> None:
        self._notifier = notifier
        self._lock = lock
        self._recipient_id = recipient_id

    async def remind(self, now: datetime) -> bool:
        if not self._recipient_id:
            return False
        day = now.astimezone(TZ).date()
        # Ключ переживает перезапуск бота; отдельный ключ даты не мешает следующему дню.
        key = f"content_reminder:{self._recipient_id}:{day.isoformat()}"
        if not await self._lock.acquire(key, ttl_seconds=172800):
            return False
        try:
            await self._notifier.notify_user(
                self._recipient_id, _MESSAGES[day.toordinal() % len(_MESSAGES)]
            )
        except (RecipientUnreachableError, TelegramTemporarilyUnavailableError):
            logger.exception("Не доставлено напоминание редактору %s", self._recipient_id)
            return False
        return True
