from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from app.api.schemas.quest import AnswerIn, BuildIn, RunOut
from app.domain.quest.channel import render_ranking
from app.domain.quest.game import (
    BUILDINGS,
    QUESTION_BY_ID,
    QUESTS,
    AnswerOutcome,
    BuildOutcome,
    Progress,
    RankEntry,
    Run,
    answer_run,
    daily_questions,
    game_day,
    upgrade_village,
)
from app.domain.subscription.weekly import week_start

NOW = datetime(2026, 11, 10, 12, tzinfo=UTC)


def make_run() -> Run:
    return Run("run", 42, "forest", game_day(NOW), daily_questions(QUESTS[0], 42, game_day(NOW)))


def test_perfect_run_has_bounded_reward_and_cannot_be_replayed() -> None:
    run = make_run()
    for index, question_id in enumerate(run.question_ids):
        result = answer_run(run, index, QUESTION_BY_ID[question_id].answer, NOW)
        assert result.outcome == AnswerOutcome.CORRECT
        run = result.run
    assert run.complete and run.points == 100
    duplicate = answer_run(run, 2, "Дос", NOW)
    assert duplicate.run == run and duplicate.outcome == AnswerOutcome.REPLAY


def test_wrong_answer_lowers_reward_and_retry_is_idempotent() -> None:
    run = make_run()
    q = QUESTION_BY_ID[run.question_ids[0]]
    wrong = next(option for option in q.options if option != q.answer)
    result = answer_run(run, 0, wrong, NOW)
    assert result.outcome == AnswerOutcome.WRONG
    assert answer_run(result.run, 0, wrong, NOW).outcome == AnswerOutcome.REPLAY
    correct = answer_run(result.run, 0, q.answer, NOW)
    assert correct.run.points == 10
    assert correct.run.tried == ()


def test_stale_index_returns_current_state_without_awarding_again() -> None:
    run = make_run()
    value = QUESTION_BY_ID[run.question_ids[0]].answer
    advanced = answer_run(run, 0, value, NOW).run
    retry = answer_run(advanced, 0, value, NOW)
    assert retry.run == advanced
    assert retry.outcome == AnswerOutcome.REPLAY


@pytest.mark.parametrize("index,value", [(1, "Орман"), (0, "bogus"), (5, "Орман")])
def test_invalid_question_or_answer_never_changes_run(index: int, value: str) -> None:
    run = make_run()
    result = answer_run(run, index, value, NOW)
    assert result.run == run and result.outcome == AnswerOutcome.INVALID


def test_daily_limit_and_week_follow_almaty_midnight() -> None:
    before = datetime(2026, 11, 15, 18, 59, tzinfo=UTC)
    after = before + timedelta(minutes=1)
    assert game_day(before) == date(2026, 11, 15)
    assert game_day(after) == date(2026, 11, 16)
    assert week_start(after) == date(2026, 11, 16)
    run = replace(make_run(), day=game_day(before))
    assert (
        answer_run(run, 0, QUESTION_BY_ID[run.question_ids[0]].answer, after).outcome
        == AnswerOutcome.EXPIRED
    )


def test_question_selection_is_stable_unique_and_bounded() -> None:
    for quest in QUESTS:
        selected = daily_questions(quest, 42, game_day(NOW))
        assert selected == daily_questions(quest, 42, game_day(NOW))
        assert len(selected) == len(set(selected)) == 3
        assert set(selected) <= {q.id for q in quest.questions}


def test_answer_key_is_not_in_run_response() -> None:
    response = RunOut.of(make_run()).model_dump()
    assert response["question"]
    assert set(response["question"]) == {"prompt", "options", "tried"}


@pytest.mark.parametrize(
    "body",
    [
        {"question_index": 0, "answer": "Орман", "points": 1000000},
        {"question_index": True, "answer": "Орман"},
        {"question_index": -1, "answer": "Орман"},
        {"question_index": 0, "answer": "x" * 65},
    ],
)
def test_client_cannot_submit_scores_or_unbounded_answers(body: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        AnswerIn.model_validate(body)


def test_build_is_idempotent_and_cannot_skip_levels_or_overspend() -> None:
    original = Progress(wood=25, stone=10)
    outcome, built = upgrade_village(original, "yurt", 1)
    assert outcome == BuildOutcome.BUILT
    assert (built.wood, built.stone, dict(built.buildings)) == (0, 0, {"yurt": 1})
    assert upgrade_village(built, "yurt", 1) == (BuildOutcome.REPLAY, built)
    assert upgrade_village(built, "yurt", 2) == (BuildOutcome.INSUFFICIENT, built)
    assert upgrade_village(original, "yurt", 3) == (BuildOutcome.INVALID, original)
    assert upgrade_village(original, "bank", 1) == (BuildOutcome.INVALID, original)


def test_all_buildings_have_three_reachable_levels() -> None:
    progress = Progress(wood=1000, stone=1000)
    for building in BUILDINGS:
        for target in range(1, 4):
            result, progress = upgrade_village(progress, building.id, target)
            assert result == BuildOutcome.BUILT
        assert upgrade_village(progress, building.id, 4)[0] == BuildOutcome.INVALID
    assert sum(dict(progress.buildings).values()) == 9
    with pytest.raises(ValueError):
        BuildIn(building_id="yurt", target_level=True)


def test_public_ranking_uses_pseudonyms_and_explicit_period() -> None:
    entry = RankEntry(123456789, 1, 100)
    text = render_ranking((entry,), date(2026, 11, 9), final=True)
    assert "123456789" not in text
    assert "Саяхатшы" in text and "Апта жеңімпаздары" in text
    assert "09.11 — 15.11.2026" in text and "100" in text
