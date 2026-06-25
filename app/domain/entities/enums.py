"""Доменные перечисления."""

from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    NEW = "new"                       # только нажал /start
    PENDING_REVIEW = "pending_review"  # отправил чек, ждёт модерации
    ACTIVE = "active"                  # подписка активна
    EXPIRED = "expired"                # срок вышел


class PaymentMethod(StrEnum):
    KASPI = "kaspi"   # ручной перевод + скриншот чека
    STARS = "stars"   # Telegram Stars (в т.ч. авто-подписка)
    FIAT = "fiat"     # платёжный провайдер (KZT на ИП) — задел


class PaymentStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
