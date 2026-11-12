from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from app.application.ports.telegram import RecipientUnreachableError, TelegramNotifier
from app.application.services.content_reminder_service import ContentReminderService
from app.infrastructure.scheduler import build_scheduler

_NOW = datetime(2026, 11, 12, 7, 45, tzinfo=UTC)


class DailyLock:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    async def acquire(self, key: str, ttl_seconds: int) -> bool:
        if key in self.keys:
            return False
        self.keys.add(key)
        return True


async def test_reminder_is_private_and_does_not_repeat_after_service_restart() -> None:
    notifier = AsyncMock(spec=TelegramNotifier)
    lock = DailyLock()
    service = ContentReminderService(notifier, lock, 123)
    assert await service.remind(_NOW)
    restarted = ContentReminderService(notifier, lock, 123)
    assert not await restarted.remind(_NOW)
    assert await restarted.remind(_NOW + timedelta(days=1))
    calls = notifier.notify_user.call_args_list
    assert len(calls) == 2
    assert all(call.args[0] == 123 for call in calls)
    assert calls[0].args[1] != calls[1].args[1]
    assert all("/add" in call.args[1] for call in calls)
    notifier.notify_admins.assert_not_called()


async def test_disabled_reminder_does_not_send() -> None:
    notifier = AsyncMock(spec=TelegramNotifier)
    assert not await ContentReminderService(notifier, DailyLock(), 0).remind(_NOW)
    notifier.notify_user.assert_not_called()


async def test_unreachable_editor_is_logged_without_crashing_job() -> None:
    notifier = AsyncMock(spec=TelegramNotifier)
    notifier.notify_user.side_effect = RecipientUnreachableError("blocked")
    assert not await ContentReminderService(notifier, DailyLock(), 123).remind(_NOW)


def test_reminder_runs_at_1245_almaty() -> None:
    scheduler = build_scheduler(AsyncMock())
    job = scheduler.get_job("content_reminder")
    assert job.trigger.get_next_fire_time(None, _NOW - timedelta(minutes=1)) == _NOW
    assert job.coalesce
    assert job.max_instances == 1
