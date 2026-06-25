"""Базовый класс ORM-моделей (SQLAlchemy 2.0 Declarative)."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
