from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.application.ports.quest import QuestRepository
from app.domain.quest.game import (
    QUEST_BY_ID,
    QUESTS,
    AnswerResult,
    BuildOutcome,
    Progress,
    Run,
    answer_run,
    daily_questions,
    game_day,
    upgrade_village,
)
from app.domain.subscription.weekly import week_start


class QuestService:
    def __init__(self, repository: QuestRepository) -> None:
        self._repository = repository

    async def progress(self, user_id: int, now: datetime) -> Progress:
        return await self._repository.progress(user_id, game_day(now))

    async def start(self, user_id: int, quest_id: str, now: datetime) -> Run | None:
        quest = QUEST_BY_ID.get(quest_id)
        if quest is None:
            return None
        progress = await self.progress(user_id, now)
        previous = QUESTS[: QUESTS.index(quest)]
        if any(q.id not in progress.completed_quests for q in previous):
            return None
        day = game_day(now)
        return await self._repository.start(
            Run(
                str(uuid4()),
                user_id,
                quest_id,
                day,
                daily_questions(quest, user_id, day),
            )
        )

    async def answer(
        self,
        user_id: int,
        run_id: str,
        index: int,
        answer: str,
        now: datetime,
    ) -> AnswerResult | None:
        # Проверка и начисление находятся в одной транзакции под блокировкой строки.
        async with self._repository.locked_run(run_id, user_id) as run:
            if run is None:
                return None
            result = answer_run(run, index, answer, now)
            if result.run != run:
                await self._repository.save_answer(result.run, week_start(now))
            return result

    async def build(
        self,
        user_id: int,
        building_id: str,
        target_level: int,
    ) -> BuildOutcome:
        async with self._repository.locked_village(user_id) as progress:
            outcome, updated = upgrade_village(progress, building_id, target_level)
            if outcome == BuildOutcome.BUILT:
                await self._repository.save_village(user_id, updated)
            return outcome
