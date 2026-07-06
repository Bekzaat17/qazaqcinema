"""ASGI-приложение FastAPI (точка входа API). Запуск: uvicorn app.api.app:app."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from app.api.routers import auth, catalog, health, me, payments
from app.config.settings import load_config
from app.infrastructure.di.providers import build_container

_log = logging.getLogger("qazaqcinema.api")


async def _ping_redis(container: AsyncContainer) -> None:
    """Health-ping Redis на старте. Fail-open: недоступность не роняет API."""
    try:
        redis = await container.get(Redis)
        await redis.ping()
        _log.info("Redis подключён")
    except Exception as exc:
        _log.warning("Redis недоступен на старте (fail-open): %s", exc)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    await _ping_redis(app.state.dishka_container)
    yield
    await app.state.dishka_container.close()


def create_app(container: AsyncContainer | None = None) -> FastAPI:
    config = load_config()
    app = FastAPI(title="QazaqCinema API", version="0.1.0", lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(catalog.router)
    app.include_router(payments.router)
    app.include_router(me.router)
    app.include_router(health.router)

    # Постеры — статика на диске (см. LocalPosterStorage). Каталог создаём заранее,
    # иначе StaticFiles упадёт при старте, пока постеров ещё нет. В проде эту раздачу
    # берёт на себя Nginx (Фаза 10).
    posters_dir = Path(config.media.root) / "posters"
    posters_dir.mkdir(parents=True, exist_ok=True)
    app.mount(config.media.posters_url_base, StaticFiles(directory=posters_dir), name="posters")

    setup_dishka(container or build_container(), app)
    return app


app = create_app()
