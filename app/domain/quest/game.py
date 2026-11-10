from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import StrEnum
from hashlib import sha256

from app.domain.catalog.daily import TZ


class AnswerOutcome(StrEnum):
    CORRECT = "correct"
    WRONG = "wrong"
    REPLAY = "replay"
    EXPIRED = "expired"
    INVALID = "invalid"


class RankingPeriod(StrEnum):
    WEEK = "week"
    ALL = "all"


class BuildOutcome(StrEnum):
    BUILT = "built"
    REPLAY = "replay"
    INSUFFICIENT = "insufficient"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    prompt: str
    options: tuple[str, ...]
    answer: str
    explanation: str


@dataclass(frozen=True, slots=True)
class Quest:
    id: str
    name: str
    questions: tuple[Question, ...]


QUESTS = (
    Quest(
        "forest",
        "Орман рухы",
        (
            Question(
                "forest_1",
                "«Лес» қазақша қалай аталады?",
                ("Орман", "Теңіз", "Қала"),
                "Орман",
                "Орман — ағаштар өсетін табиғи мекен.",
            ),
            Question(
                "forest_2",
                "«Дерево» сөзінің аудармасын тап.",
                ("Тас", "Ағаш", "Бұлт"),
                "Ағаш",
                "Ағаш — дерево. Ағаштар ауаны тазартады.",
            ),
            Question(
                "forest_3",
                "Қай сөз «друг» дегенді білдіреді?",
                ("Жол", "Түн", "Дос"),
                "Дос",
                "Дос — друг. Достық — үлкен байлық.",
            ),
            Question(
                "forest_4",
                "«Жапырақ» орысша қалай аталады?",
                ("Лист", "Корень", "Цветок"),
                "Лист",
                "Жапырақ — лист, тамыр — корень.",
            ),
        ),
    ),
    Quest(
        "river",
        "Бұлақ рухы",
        (
            Question(
                "river_1",
                "«Вода» сөзінің аудармасын тап.",
                ("От", "Су", "Жер"),
                "Су",
                "Су — тіршілік көзі.",
            ),
            Question(
                "river_2",
                "«Родник» қазақша қалай аталады?",
                ("Бұлақ", "Тау", "Дала"),
                "Бұлақ",
                "Бұлақ — жер астынан шығатын су көзі.",
            ),
            Question(
                "river_3",
                "«Таза су» тіркесінің мағынасы қандай?",
                ("Тёплая вода", "Чистая вода", "Море"),
                "Чистая вода",
                "Таза — чистый. Таза суды қорғауымыз керек.",
            ),
            Question(
                "river_4",
                "«Река» қазақша қалай аталады?",
                ("Көл", "Жаңбыр", "Өзен"),
                "Өзен",
                "Өзен — река, көл — озеро.",
            ),
        ),
    ),
    Quest(
        "sky",
        "Аспан рухы",
        (
            Question(
                "sky_1",
                "«Небо» қазақша қалай аталады?",
                ("Аспан", "Орман", "Бұлақ"),
                "Аспан",
                "Аспан — небо. Көк аспан — голубое небо.",
            ),
            Question(
                "sky_2",
                "«Жұлдыз» сөзінің аудармасын тап.",
                ("Луна", "Солнце", "Звезда"),
                "Звезда",
                "Жұлдыз — звезда, ай — луна, күн — солнце.",
            ),
            Question(
                "sky_3",
                "«Арман» орысша қалай аталады?",
                ("Мечта", "Дождь", "Дорога"),
                "Мечта",
                "Арман — мечта. Арманыңа қарай қадам жаса!",
            ),
            Question(
                "sky_4",
                "«Жел» сөзінің аудармасын тап.",
                ("Снег", "Ветер", "Облако"),
                "Ветер",
                "Жел — ветер, қар — снег, бұлт — облако.",
            ),
        ),
    ),
)
QUEST_BY_ID = {quest.id: quest for quest in QUESTS}
QUESTION_BY_ID = {q.id: q for quest in QUESTS for q in quest.questions}
QUESTIONS_PER_RUN = 3
FIRST_TRY_POINTS = 30
RETRY_POINTS = 10
COMPLETION_POINTS = 10
LEADERBOARD_TTL = 300
WOOD_REWARD = 25
STONE_REWARD = 15


@dataclass(frozen=True, slots=True)
class Building:
    id: str
    name: str
    costs: tuple[tuple[int, int], ...]


BUILDINGS = (
    Building("yurt", "Киіз үй", ((25, 10), (45, 25), (70, 40))),
    Building("well", "Құдық", ((20, 20), (40, 35), (60, 50))),
    Building("workshop", "Шеберхана", ((35, 15), (55, 30), (80, 45))),
)
BUILDING_BY_ID = {building.id: building for building in BUILDINGS}


def game_day(now: datetime) -> date:
    return now.astimezone(TZ).date()


def daily_questions(quest: Quest, user_id: int, day: date) -> tuple[str, ...]:
    """Стабильный набор на сутки: новый запрос не позволяет перебросить вопросы."""
    seed = f"{user_id}:{day}:{quest.id}"
    ordered = sorted(quest.questions, key=lambda q: sha256(f"{seed}:{q.id}".encode()).digest())
    return tuple(q.id for q in ordered[:QUESTIONS_PER_RUN])


@dataclass(frozen=True, slots=True)
class Run:
    id: str
    user_id: int
    quest_id: str
    day: date
    question_ids: tuple[str, ...]
    index: int = 0
    tried: tuple[str, ...] = ()
    points: int = 0

    @property
    def complete(self) -> bool:
        return self.index == len(self.question_ids)


@dataclass(frozen=True, slots=True)
class AnswerResult:
    run: Run
    outcome: AnswerOutcome
    explanation: str | None = None


def answer_run(run: Run, index: int, answer: str, now: datetime) -> AnswerResult:
    if run.complete or index < run.index:
        return AnswerResult(run, AnswerOutcome.REPLAY)
    if run.day != game_day(now):
        return AnswerResult(run, AnswerOutcome.EXPIRED)
    if index != run.index:
        return AnswerResult(run, AnswerOutcome.INVALID)
    question = QUESTION_BY_ID[run.question_ids[index]]
    if answer not in question.options:
        return AnswerResult(run, AnswerOutcome.INVALID)
    if answer in run.tried:
        return AnswerResult(run, AnswerOutcome.REPLAY)
    if answer != question.answer:
        return AnswerResult(replace(run, tried=(*run.tried, answer)), AnswerOutcome.WRONG)
    points = RETRY_POINTS if run.tried else FIRST_TRY_POINTS
    if index + 1 == len(run.question_ids):
        points += COMPLETION_POINTS
    updated = replace(run, index=index + 1, tried=(), points=run.points + points)
    return AnswerResult(updated, AnswerOutcome.CORRECT, question.explanation)


@dataclass(frozen=True, slots=True)
class Progress:
    total_xp: int = 0
    completed_quests: tuple[str, ...] = ()
    completed_today: tuple[str, ...] = ()
    wood: int = 0
    stone: int = 0
    buildings: tuple[tuple[str, int], ...] = ()


def upgrade_village(
    progress: Progress,
    building_id: str,
    target_level: int,
) -> tuple[BuildOutcome, Progress]:
    building = BUILDING_BY_ID.get(building_id)
    levels = dict(progress.buildings)
    current = levels.get(building_id, 0)
    if building is None or target_level < 1 or target_level > len(building.costs):
        return BuildOutcome.INVALID, progress
    if target_level <= current:
        return BuildOutcome.REPLAY, progress
    if target_level != current + 1:
        return BuildOutcome.INVALID, progress
    wood, stone = building.costs[current]
    if progress.wood < wood or progress.stone < stone:
        return BuildOutcome.INSUFFICIENT, progress
    levels[building_id] = target_level
    return BuildOutcome.BUILT, replace(
        progress,
        wood=progress.wood - wood,
        stone=progress.stone - stone,
        buildings=tuple(levels.items()),
    )


@dataclass(frozen=True, slots=True)
class RankEntry:
    user_id: int
    rank: int
    points: int

    @property
    def name(self) -> str:
        # Публичный псевдоним не раскрывает имя или username из Telegram.
        suffix = sha256(f"quest-player:{self.user_id}".encode()).hexdigest()[:6].upper()
        return f"Саяхатшы {suffix}"
