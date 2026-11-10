from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.quest.game import BUILDINGS, QUESTION_BY_ID, Progress, RankEntry, Run


class StartQuestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quest_id: str = Field(min_length=1, max_length=32)


class AnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_index: int = Field(ge=0, le=2, strict=True)
    answer: str = Field(min_length=1, max_length=64)


class BuildIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    building_id: str = Field(min_length=1, max_length=32)
    target_level: int = Field(ge=1, le=3, strict=True)


class BuildingOut(BaseModel):
    id: str
    name: str
    level: int
    wood_cost: int | None
    stone_cost: int | None


class ProgressOut(BaseModel):
    total_xp: int
    level: int
    completed_quests: list[str]
    completed_today: list[str]
    wood: int
    stone: int
    buildings: list[BuildingOut]

    @classmethod
    def of(cls, progress: Progress) -> ProgressOut:
        levels = dict(progress.buildings)
        buildings = []
        for building in BUILDINGS:
            level = levels.get(building.id, 0)
            cost = building.costs[level] if level < len(building.costs) else None
            buildings.append(
                BuildingOut(
                    id=building.id,
                    name=building.name,
                    level=level,
                    wood_cost=cost[0] if cost else None,
                    stone_cost=cost[1] if cost else None,
                )
            )
        return cls(
            total_xp=progress.total_xp,
            level=1 + progress.total_xp // 300,
            completed_quests=list(progress.completed_quests),
            completed_today=list(progress.completed_today),
            wood=progress.wood,
            stone=progress.stone,
            buildings=buildings,
        )


class QuestionOut(BaseModel):
    prompt: str
    options: list[str]
    tried: list[str]


class RunOut(BaseModel):
    id: str
    quest_id: str
    question_index: int
    total_questions: int
    points: int
    complete: bool
    question: QuestionOut | None

    @classmethod
    def of(cls, run: Run) -> RunOut:
        question = None
        if not run.complete:
            current = QUESTION_BY_ID[run.question_ids[run.index]]
            # Не отдаём ключ ответа и не используем исходный порядок вариантов.
            options = sorted(current.options, key=lambda value: value[::-1])
            question = QuestionOut(prompt=current.prompt, options=options, tried=list(run.tried))
        return cls(
            id=run.id,
            quest_id=run.quest_id,
            question_index=run.index,
            total_questions=len(run.question_ids),
            points=run.points,
            complete=run.complete,
            question=question,
        )


class AnswerOut(BaseModel):
    run: RunOut
    outcome: str
    explanation: str | None
    progress: ProgressOut


class RankOut(BaseModel):
    rank: int
    name: str
    points: int
    is_self: bool

    @classmethod
    def of(cls, row: RankEntry, user_id: int) -> RankOut:
        return cls(rank=row.rank, name=row.name, points=row.points, is_self=row.user_id == user_id)


class RankingOut(BaseModel):
    leaders: list[RankOut]
    me: RankOut | None
    refresh_seconds: int = 300
