"""GET /api/health — живость сервиса: ping Redis + БД. Для мониторинга и прод-проверок.

Не требует авторизации. Fail-soft: недоступность зависимости не роняет ручку —
возвращаем её статус (`down`) и общий `degraded`, а не 500.
"""

from __future__ import annotations

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/health", tags=["health"], route_class=DishkaRoute)


@router.get("")
async def health(
    redis: FromDishka[Redis],
    session: FromDishka[AsyncSession],
) -> dict[str, str]:
    checks: dict[str, str] = {}

    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "down"

    try:
        await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "down"

    checks["status"] = "ok" if checks["redis"] == "ok" and checks["db"] == "ok" else "degraded"
    return checks
