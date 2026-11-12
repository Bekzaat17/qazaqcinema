from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from app.application.ports.game_analytics import GameAnalyticsRepository
from app.application.ports.telegram import RecipientUnreachableError, TelegramNotifier
from app.application.services.boardgame_service import BoardGameService
from app.application.services.game_analytics_service import GameAnalyticsService
from app.domain.analytics.events import EventKind
from app.domain.analytics.game_report import GameReport, GameWinner, render_game_report
from app.domain.boardgame.game import Action, Command, Outcome
from app.domain.catalog.daily import TZ
from app.domain.entities.user import User
from app.infrastructure.db.models import UserEventModel
from app.infrastructure.db.quest_models import BoardResultModel, QuestRunModel
from app.infrastructure.db.repositories.boardgame import PgRoomRepository
from app.infrastructure.db.repositories.game_analytics import PgGameAnalyticsRepository
from app.infrastructure.db.repositories.users import PgUserRepository
from app.infrastructure.scheduler import build_scheduler
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fakes import FakeEvents
from tests.test_boardgame_repositories import CATALOG, Events, FixedRandom
from tests.test_content_reminder import DailyLock

_NOW = datetime(2026, 11, 12, 17, 5, tzinfo=UTC)


async def test_daily_game_report_is_private_disabled_by_default_and_deduplicated() -> None:
    repository = AsyncMock(spec=GameAnalyticsRepository)
    repository.report.return_value = GameReport(_NOW - timedelta(days=1), _NOW)
    notifier = AsyncMock(spec=TelegramNotifier)
    lock = DailyLock()
    assert not await GameAnalyticsService(repository, notifier, lock, 0).send_daily(_NOW)
    repository.report.assert_not_called()
    assert await GameAnalyticsService(repository, notifier, lock, 123).send_daily(_NOW)
    assert not await GameAnalyticsService(repository, notifier, lock, 123).send_daily(_NOW)
    notifier.notify_user.assert_awaited_once()
    assert notifier.notify_user.call_args.args[0] == 123
    notifier.notify_admins.assert_not_called()
    repository.report.assert_awaited_with(_NOW - timedelta(days=1), _NOW)


async def test_unreachable_game_report_recipient_does_not_crash_scheduler() -> None:
    repository = AsyncMock(spec=GameAnalyticsRepository)
    repository.report.return_value = GameReport(_NOW - timedelta(days=1), _NOW)
    notifier = AsyncMock(spec=TelegramNotifier)
    notifier.notify_user.side_effect = RecipientUnreachableError("blocked")
    assert not await GameAnalyticsService(repository, notifier, DailyLock(), 123).send_daily(_NOW)


def test_game_report_schedule_is_2205_almaty_and_configurable() -> None:
    scheduler = build_scheduler(AsyncMock())
    job = scheduler.get_job("game_report")
    assert job.trigger.get_next_fire_time(None, _NOW - timedelta(minutes=1)) == _NOW
    assert job.coalesce and job.max_instances == 1
    other = build_scheduler(AsyncMock(), game_report_hour=23, game_report_minute=5)
    assert other.get_job("game_report").trigger.get_next_fire_time(None, _NOW) == (
        _NOW + timedelta(hours=1)
    )


def test_game_report_escapes_names_and_proposes_feedback_without_false_conversion() -> None:
    report = GameReport(
        _NOW - timedelta(days=1), _NOW,
        games_started=1, games_finished=2, winners=(GameWinner("<b>Аян</b>", 2),),
    )
    text = render_game_report(report)
    assert "&lt;b&gt;Аян&lt;/b&gt;" in text
    assert "собрать отзывы" in text
    assert "200%" not in text
    assert len(text) < 4096


async def test_board_events_only_follow_committed_human_actions(session: AsyncSession) -> None:
    await PgUserRepository(session).upsert(User(telegram_id=42))
    analytics = FakeEvents()
    game = BoardGameService(
        PgRoomRepository(session), CATALOG, FixedRandom(), Events(), analytics=analytics,
    )
    room = await game.create(42, "Аян", "almaty_first")
    assert room
    assert analytics.kinds_for(42) == [EventKind.BOARD_CREATE]
    await game.command(42, room.code, Command(0, Action.ADD_BOT, "balanced"), _NOW)
    result = await game.command(42, room.code, Command(1, Action.START), _NOW)
    assert result.outcome == Outcome.APPLIED
    assert analytics.kinds_for(42)[-1] == EventKind.BOARD_START
    before = len(analytics.added)
    await game.command(42, room.code, Command(1, Action.START), _NOW)
    await game.command(42, room.code, Command(2, Action.TIMEOUT), _NOW + timedelta(seconds=181))
    assert len(analytics.added) == before


async def test_game_counts_deduplicate_parties_exclude_admins_and_use_half_open_window(
    session: AsyncSession,
) -> None:
    for uid in (42, 43, 99):
        await PgUserRepository(session).upsert(User(telegram_id=uid))
    game = BoardGameService(PgRoomRepository(session), CATALOG, FixedRandom(), Events())
    room = await game.create(42, "Аян", "almaty_first")
    assert room
    since = _NOW - timedelta(days=1)
    for uid, kind, when in (
        (42, EventKind.BOARD_CREATE, since),
        (42, EventKind.BOARD_START, since),
        (43, EventKind.BOARD_START, since),
        (99, EventKind.BOARD_ACTION, since),
        (99, EventKind.BOARD_CREATE, since),
        (43, EventKind.BOARD_ACTION, _NOW),
        (43, EventKind.BOARD_CREATE, since - timedelta(seconds=1)),
    ):
        session.add(UserEventModel(user_id=uid, kind=kind.value, meta=room.code, created_at=when))
    for uid in (42, 43, 99):
        session.add(BoardResultModel(
            code=room.code, user_id=uid, name=f"Игрок {uid}", scenario_id="almaty_first",
            board_id="almaty", rounds=10, finished_at=since,
            winner_name="Игрок 42", player_count=3, capital=1000, won=uid == 42,
        ))
        session.add(QuestRunModel(
            id=f"run-{uid}", user_id=uid, quest_id="quest", day=_NOW.astimezone(TZ).date(),
            question_ids=["a", "b"], question_index=2 if uid != 43 else 1,
        ))
    await session.commit()
    report = await PgGameAnalyticsRepository(session, (99,)).report(since, _NOW)
    assert (report.active_players, report.rooms_created, report.games_started) == (2, 1, 1)
    assert (report.games_finished, report.finished_players) == (1, 2)
    assert (report.quest_players, report.quests_started, report.quests_finished) == (2, 2, 1)
    assert report.winners == (GameWinner("Игрок 42", 1),)
