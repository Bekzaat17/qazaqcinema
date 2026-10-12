"""Режим объявлений о новом фильме при добавлении в каталог."""

from __future__ import annotations

from enum import StrEnum


class NotificationMode(StrEnum):
    ALL = "1"
    CHANNEL_ONLY = "0"
    NONE = "none"
