"""Ручное открытие доступа из обращения без повторного продления от двойного клика."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.application.ports.repositories import UserRepository
from app.application.ports.telegram import (
    RecipientUnreachableError,
    TelegramTemporarilyUnavailableError,
)
from app.application.services.subscription_service import SubscriptionService
from app.domain.tariffs.catalog import get_tariff


class SupportAccessOutcome(StrEnum):
    GRANTED = "granted"
    ALREADY_OPEN = "already_open"
    NOT_FOUND = "not_found"
    UNKNOWN_TARIFF = "unknown_tariff"
    GRANTED_UNNOTIFIED = "granted_unnotified"


@dataclass(frozen=True, slots=True)
class SupportAccessResult:
    outcome: SupportAccessOutcome
    expires_at: datetime | None = None


class SupportAccessService:
    def __init__(self, users: UserRepository, subscription: SubscriptionService) -> None:
        self._users = users
        self._subscription = subscription

    async def grant(self, user_id: int, tariff_slug: str, now: datetime) -> SupportAccessResult:
        tariff = get_tariff(tariff_slug)
        if tariff is None:
            return SupportAccessResult(SupportAccessOutcome.UNKNOWN_TARIFF)
        user = await self._users.get_for_update(user_id)
        if user is None:
            return SupportAccessResult(SupportAccessOutcome.NOT_FOUND)
        # Кнопка открывает доступ, а не докупает такой же период при каждом нажатии.
        # Более длинную действующую подписку короткая кнопка тоже не меняет.
        if user.has_active_access(now) and (
            user.selected_tariff == tariff_slug
            or (user.expires_at is not None and user.expires_at >= now + tariff.duration)
        ):
            return SupportAccessResult(SupportAccessOutcome.ALREADY_OPEN, user.expires_at)
        try:
            await self._subscription.activate(user, tariff, now)
        except (RecipientUnreachableError, TelegramTemporarilyUnavailableError):
            # activate сохраняет доступ ДО уведомления: повторять грант из-за DM нельзя.
            return SupportAccessResult(SupportAccessOutcome.GRANTED_UNNOTIFIED, user.expires_at)
        return SupportAccessResult(SupportAccessOutcome.GRANTED, user.expires_at)
