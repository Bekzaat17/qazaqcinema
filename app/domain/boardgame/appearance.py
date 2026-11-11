"""Варианты портрета без определения пола по имени игрока."""

from __future__ import annotations

from enum import StrEnum


class Portrait(StrEnum):
    MALE = "male"
    FEMALE = "female"
