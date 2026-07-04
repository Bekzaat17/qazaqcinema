"""Юнит-тест админ-гейта бота (чистая функция, без aiogram)."""

from __future__ import annotations

from app.bot.security import is_admin


def test_is_admin_true_for_listed_id() -> None:
    assert is_admin(42, [1, 42, 7]) is True


def test_is_admin_false_for_unlisted_id() -> None:
    assert is_admin(99, [1, 42, 7]) is False


def test_is_admin_false_for_empty_list() -> None:
    assert is_admin(42, []) is False
