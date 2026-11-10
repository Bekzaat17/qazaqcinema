from __future__ import annotations

from datetime import datetime

from app.application.ports.quest import QuestRankingCache, QuestRepository
from app.domain.quest.game import LEADERBOARD_TTL, RankEntry, RankingPeriod
from app.domain.subscription.weekly import week_start


class QuestRankingService:
    def __init__(self, repository: QuestRepository, cache: QuestRankingCache) -> None:
        self._repository = repository
        self._cache = cache

    async def leaders(
        self,
        period: RankingPeriod,
        now: datetime,
        *,
        fresh: bool = False,
    ) -> tuple[RankEntry, ...]:
        week = week_start(now)
        key = f"{period}:{week}"
        if not fresh:
            cached = await self._cache.get(key)
            if cached is not None:
                return cached
        entries = await self._repository.leaders(period, week, 10)
        await self._cache.set(key, entries, LEADERBOARD_TTL)
        return entries

    async def rank(
        self,
        user_id: int,
        period: RankingPeriod,
        now: datetime,
    ) -> RankEntry | None:
        return await self._repository.rank(user_id, period, week_start(now))
