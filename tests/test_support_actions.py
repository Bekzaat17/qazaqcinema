"""Ответ поддержки и ручной грант: доставка, сроки и защита от повторного нажатия."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from app.application.ports.repositories import UserEventRepository, UserRepository
from app.application.ports.telegram import (
    RecipientUnreachableError,
    TelegramNotifier,
    TelegramTemporarilyUnavailableError,
)
from app.application.services.subscription_service import SubscriptionService
from app.application.services.support_access_service import (
    SupportAccessOutcome,
    SupportAccessService,
)
from app.application.services.support_service import (
    MAX_REPLY_LEN,
    EmptySupportMessageError,
    SupportReplyTooLongError,
    SupportService,
)
from app.application.services.video_retention_service import VideoRetentionService
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User

_NOW = datetime(2026, 11, 5, tzinfo=UTC)


class SupportActionsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.user = User(telegram_id=8889467653)
        self.users = AsyncMock(spec=UserRepository)
        self.users.get_for_update.return_value = self.user
        self.users.upsert.side_effect = lambda user: user
        self.notifier = AsyncMock(spec=TelegramNotifier)
        self.events = AsyncMock(spec=UserEventRepository)
        self.subscription = SubscriptionService(
            self.users, self.notifier, AsyncMock(spec=VideoRetentionService), self.events
        )
        self.access = SupportAccessService(self.users, self.subscription)
        self.support = SupportService(self.notifier)

    async def test_reply_goes_only_to_the_author_as_plain_text(self) -> None:
        await self.support.reply(self.user.telegram_id, "  5 < 6 & сұрақ  ")
        self.notifier.notify_user.assert_awaited_once_with(
            self.user.telegram_id, "💬 Қолдау қызметінің жауабы:\n\n5 < 6 & сұрақ"
        )
        self.notifier.notify_admins.assert_not_awaited()

    async def test_empty_and_long_reply_are_not_sent(self) -> None:
        for text, error in [
            ("  \n", EmptySupportMessageError),
            ("x" * (MAX_REPLY_LEN + 1), SupportReplyTooLongError),
            ("🎬" * (MAX_REPLY_LEN // 2 + 1), SupportReplyTooLongError),
        ]:
            with self.assertRaises(error):
                await self.support.reply(self.user.telegram_id, text)
        self.notifier.notify_user.assert_not_awaited()

    async def test_delivery_failure_is_not_reported_as_success(self) -> None:
        for error in (RecipientUnreachableError, TelegramTemporarilyUnavailableError):
            self.notifier.notify_user.side_effect = error("undelivered")
            with self.assertRaises(error):
                await self.support.reply(self.user.telegram_id, "жауап")

    async def test_day_and_month_grants_use_the_subscription_engine(self) -> None:
        for slug, days in [("1_day", 1), ("1_month", 30)]:
            self.user.status = UserStatus.NEW
            self.user.expires_at = None
            result = await self.access.grant(self.user.telegram_id, slug, _NOW)
            self.assertEqual(result.outcome, SupportAccessOutcome.GRANTED)
            self.assertEqual(result.expires_at, _NOW + timedelta(days=days))
            self.assertTrue(self.user.has_active_access(_NOW))
            self.assertEqual(self.user.selected_tariff, slug)
        self.assertEqual(self.events.add.await_count, 2)
        self.assertEqual(self.notifier.notify_user.await_count, 2)

    async def test_repeated_grant_does_not_extend_access(self) -> None:
        first = await self.access.grant(self.user.telegram_id, "1_month", _NOW)
        second = await self.access.grant(
            self.user.telegram_id, "1_month", _NOW + timedelta(minutes=1)
        )
        self.assertEqual(second.outcome, SupportAccessOutcome.ALREADY_OPEN)
        self.assertEqual(second.expires_at, first.expires_at)
        self.users.upsert.assert_awaited_once()

    async def test_day_button_preserves_existing_month(self) -> None:
        first = await self.access.grant(self.user.telegram_id, "1_month", _NOW)
        second = await self.access.grant(self.user.telegram_id, "1_day", _NOW)
        self.assertEqual(second.outcome, SupportAccessOutcome.ALREADY_OPEN)
        self.assertEqual(second.expires_at, first.expires_at)

    async def test_month_button_can_upgrade_day_access(self) -> None:
        await self.access.grant(self.user.telegram_id, "1_day", _NOW)
        result = await self.access.grant(self.user.telegram_id, "1_month", _NOW)
        self.assertEqual(result.outcome, SupportAccessOutcome.GRANTED)
        self.assertEqual(result.expires_at, _NOW + timedelta(days=31))

    async def test_missing_user_or_tariff_does_not_grant_access(self) -> None:
        unknown = await self.access.grant(self.user.telegram_id, "unknown", _NOW)
        self.assertEqual(unknown.outcome, SupportAccessOutcome.UNKNOWN_TARIFF)
        self.users.get_for_update.return_value = None
        missing = await self.access.grant(self.user.telegram_id, "1_day", _NOW)
        self.assertEqual(missing.outcome, SupportAccessOutcome.NOT_FOUND)
        self.users.upsert.assert_not_awaited()

    async def test_blocked_user_keeps_granted_access_without_duplicate_grant(self) -> None:
        self.notifier.notify_user.side_effect = RecipientUnreachableError("blocked")
        first = await self.access.grant(self.user.telegram_id, "1_month", _NOW)
        second = await self.access.grant(self.user.telegram_id, "1_month", _NOW)
        self.assertEqual(first.outcome, SupportAccessOutcome.GRANTED_UNNOTIFIED)
        self.assertTrue(self.user.has_active_access(_NOW))
        self.assertEqual(second.outcome, SupportAccessOutcome.ALREADY_OPEN)
        self.users.upsert.assert_awaited_once()
