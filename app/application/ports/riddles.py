"""Атомарная запись попыток и взаимное исключение публикаций по запросу."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.channel.content.daily_riddle import MAX_ATTEMPTS


class PublicationGate(Protocol):
    def hold(self, key: str) -> AbstractAsyncContextManager[bool]:
        """Не ждёт занятую публикацию. Лок держится до выхода из контекста."""
        ...


@dataclass(frozen=True, slots=True)
class RiddleAttempt:
    attempts: int
    correct: bool
    recorded: bool

    @property
    def points(self) -> int:
        return MAX_ATTEMPTS + 1 - self.attempts if self.correct else 0


@dataclass(frozen=True, slots=True)
class RiddleRank:
    user_id: int
    name: str
    points: int
    solved: int


class RiddleAnswerRepository(Protocol):
    async def attempt(
        self, post_id: int, user_id: int, name: str, text: str, correct: bool, at: datetime,
    ) -> RiddleAttempt:
        """До трёх попыток; после верного ответа строка больше не меняется."""
        ...

    async def leaders(self, since: datetime, until: datetime) -> list[RiddleRank]:
        """Рейтинг только жұмбақ дня, по баллам; равные делят место."""
        ...
