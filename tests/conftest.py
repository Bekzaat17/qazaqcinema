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
            # Фикстура — источник истины по схеме (в проде это делает миграция).
            # drop+create обязателен: иначе старая таблица movies из прошлых прогонов
            # даёт дрейф схемы — create_all не меняет уже существующие таблицы.
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
            # В проде поисковую инфру создаёт миграция; тесты идут через create_all,
            # поэтому расширения и immutable-обёртку f_unaccent заводим здесь (иначе
            # PgMovieRepository.search упадёт — нет f_unaccent/similarity).
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
            await conn.execute(
                text(
                    "CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text "
                    "LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT "
                    "AS $$ SELECT public.unaccent('public.unaccent', $1) $$"
                )
            )
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
