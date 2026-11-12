from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.application.ports.game_analytics import GameAnalyticsRepository
from app.application.ports.lock import Lock
from app.application.ports.telegram import (
    RecipientUnreachableError,
    TelegramNotifier,
    TelegramTemporarilyUnavailableError,
)
from app.domain.analytics.game_report import GameReport, render_game_report
from app.domain.catalog.daily import TZ

logger = logging.getLogger(__name__)


class GameAnalyticsService:
    def __init__(
        self, repository: GameAnalyticsRepository, notifier: TelegramNotifier,
        lock: Lock, recipient_id: int,
    ) -> None:
        self._repository = repository
        self._notifier = notifier
        self._lock = lock
        self._recipient_id = recipient_id

    async def report(self, now: datetime) -> GameReport:
        return await self._repository.report(now - timedelta(days=1), now)

    async def send_daily(self, now: datetime) -> bool:
        if not self._recipient_id:
            return False
        report = await self.report(now)
        key = f"game_report:{self._recipient_id}:{now.astimezone(TZ).date()}"
        if not await self._lock.acquire(key, ttl_seconds=172800):
            return False
        try:
            await self._notifier.notify_user(self._recipient_id, render_game_report(report))
        except (RecipientUnreachableError, TelegramTemporarilyUnavailableError):
            logger.exception("Игровой отчёт не доставлен админу %s", self._recipient_id)
            return False
        return True
