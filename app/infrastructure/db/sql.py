"""Мелкие помощники поверх SQLAlchemy, общие для Pg-адаптеров."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import CursorResult, Executable
from sqlalchemy.ext.asyncio import AsyncSession


async def rowcount(session: AsyncSession, stmt: Executable) -> int:
    """Сколько строк реально задел UPDATE/DELETE/INSERT.

    На этом числе держатся идемпотентность звезды и защита подарка от двойной раздачи:
    «изменили ли мы что-то» — единственный честный ответ от БД, и получить его надо ИЗ
    того же запроса, что менял данные (отдельный SELECT снова открыл бы гонку).

    Приведение типа — здесь, в одном месте: `AsyncSession.execute` объявлен как
    `Result[Any]`, у которого `rowcount` нет; для DML приходит `CursorResult`, у которого
    он есть. Иначе `type: ignore` расползлись бы по всем вызовам.
    """
    result = await session.execute(stmt)
    return cast("CursorResult[Any]", result).rowcount
