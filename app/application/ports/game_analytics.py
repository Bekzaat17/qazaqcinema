from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.domain.analytics.game_report import GameReport


class GameAnalyticsRepository(Protocol):
    async def report(self, since: datetime, until: datetime) -> GameReport: ...
