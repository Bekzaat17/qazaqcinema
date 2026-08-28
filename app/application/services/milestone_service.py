"""Лента вех роста: тонкая обвязка над `MilestoneRepository` для команды `/milestone`.

Отдельный сервис, а не голый репозиторий в хендлере — по тому же соглашению, что и
`DailyMovieService`: бот-хендлеры зависят от `*Service`, не от портов напрямую.
"""

from __future__ import annotations

from datetime import datetime

from app.application.ports.repositories import MilestoneRepository
from app.domain.analytics.milestone import Milestone


class MilestoneService:
    def __init__(self, milestones: MilestoneRepository) -> None:
        self._milestones = milestones

    async def add(self, label: str, now: datetime, created_by: int) -> Milestone:
        return await self._milestones.add(label, now, created_by)

    async def list_recent(self, limit: int = 10) -> list[Milestone]:
        return await self._milestones.list_recent(limit)
