from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from app.config.settings import DatabaseConfig
from app.infrastructure.db import models  # noqa: F401  (регистрация моделей в metadata)
from app.infrastructure.db.base import Base
from app.infrastructure.db.engine import create_engine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_TABLES = "users, movies, payment_requests"


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Async-сессия к Postgres для интеграционных тестов репозиториев.

    Если БД недоступна — тесты пропускаются (юнит-тесты домена от БД не зависят).
    Таблицы очищаются после каждого теста.
    """
    engine = create_engine(DatabaseConfig().dsn)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        await engine.dispose()
        pytest.skip("PostgreSQL недоступен — интеграционные тесты репозиториев пропущены")

    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as db_session:
            yield db_session
    finally:
        async with maker() as cleanup:
            await cleanup.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))
            await cleanup.commit()
        await engine.dispose()
