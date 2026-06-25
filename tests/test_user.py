from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_active_user_has_access() -> None:
    user = User(telegram_id=1, status=UserStatus.ACTIVE, expires_at=NOW + timedelta(days=1))
    assert user.has_active_access(NOW) is True


def test_expired_user_has_no_access() -> None:
    user = User(telegram_id=1, status=UserStatus.ACTIVE, expires_at=NOW - timedelta(days=1))
    assert user.has_active_access(NOW) is False


def test_new_user_has_no_access() -> None:
    user = User(telegram_id=1, status=UserStatus.NEW)
    assert user.has_active_access(NOW) is False
