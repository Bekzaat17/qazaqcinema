"""Alembic env (async). DSN — из app.config.DatabaseConfig (BOT_TOKEN для миграций не нужен).

Переопределить DSN: alembic -x dsn=postgresql+asyncpg://user:pass@host/db
Offline DDL без подключения: alembic upgrade head --sql
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config.settings import DatabaseConfig
from app.infrastructure.db import models  # noqa: F401  (регистрирует модели в metadata)
from app.infrastructure.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _dsn() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    return x_args.get("dsn") or DatabaseConfig().dsn


def run_migrations_offline() -> None:
    context.configure(
        url=_dsn(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection: object) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)  # type: ignore[arg-type]
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_dsn())
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
