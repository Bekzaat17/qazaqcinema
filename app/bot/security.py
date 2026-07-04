"""Проверка админ-прав бота — единая точка для /add и модерации оплат."""

from __future__ import annotations


def is_admin(user_id: int, admin_ids: list[int]) -> bool:
    """True, если пользователь — админ (id в `BOT_ADMIN_USER_IDS`)."""
    return user_id in admin_ids
