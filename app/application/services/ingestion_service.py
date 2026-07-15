"""Добавление фильма в каталог. Источник — бот-визард `/add` (FSM).

Сервис чист: знает только порты (репозиторий, хранилище постеров, обработчик картинок,
нотификатор), ничего про aiogram. Видео уже лежит в канале-архиве (его file_id приходит
готовым); постер (и, если фильм на hero, горизонтальный баннер) приходят байтами,
нормализуются через `ImageProcessor` и уходят в `PosterStorage` (статика на VPS).
"""

from __future__ import annotations

import logging

from app.application.ports.catalog_cache import CatalogCache
from app.application.ports.images import HERO, POSTER, ImageProcessor
from app.application.ports.repositories import MovieRepository
from app.application.ports.storage import PosterStorage
from app.application.ports.telegram import TelegramNotifier
from app.application.services.broadcast_service import BroadcastService
from app.domain.entities.movie import Movie

logger = logging.getLogger(__name__)


class MovieIngestionService:
    def __init__(
        self,
        movies: MovieRepository,
        notifier: TelegramNotifier,
        posters: PosterStorage,
        images: ImageProcessor,
        catalog_cache: CatalogCache,
        broadcast: BroadcastService,
    ) -> None:
        self._movies = movies
        self._notifier = notifier
        self._posters = posters
        self._images = images
        self._cache = catalog_cache
        self._broadcast = broadcast

    async def ingest(
        self,
        *,
        title_kk: str,
        title_ru: str | None,
        title_original: str | None,
        category: str,
        description: str,
        year: int | None,
        rating: float | None,
        is_featured: bool,
        video_file_id: str,
        poster_bytes: bytes,
        hero_bytes: bytes | None,
    ) -> Movie:
        """Нормализовать/сохранить постер (+ hero-баннер), записать фильм, уведомить админов.

        `video_file_id` — file_id видео в канале-архиве (отдаётся ТОЛЬКО боту).
        `poster_bytes` — постер → нормализуется к 2:3 → `PosterStorage` → публичный URL.
        `hero_bytes` — горизонтальный баннер (только когда `is_featured`); None → hero берёт
        постер как фолбэк. Битую картинку `ImageProcessor` отклонит (ValueError).
        """
        poster_url = await self._posters.save(await self._images.normalize(poster_bytes, POSTER))
        hero_url: str | None = None
        if hero_bytes is not None:
            hero_url = await self._posters.save(await self._images.normalize(hero_bytes, HERO))
        movie = Movie(
            title_kk=title_kk,
            title_ru=title_ru,
            title_original=title_original,
            category=category,
            description=description,
            poster_url=poster_url,
            telegram_file_id=video_file_id,
            year=year,
            rating=rating,
            is_featured=is_featured,
            hero_image_url=hero_url,
        )
        saved = await self._movies.add(movie)
        # Сбрасываем ВЕСЬ кэш каталога (главная/чипы/страницы браузинга), иначе новинка не
        # видна до истечения TTL (Фаза 11.2/13; invalidate чистит весь namespace catalog:*).
        await self._cache.invalidate()
        # Тоже в try/except: notify_admins шлёт КАЖДОМУ из BOT_ADMIN_USER_IDS, а админ,
        # не нажавший /start (или заблокировавший бота), даёт 403 — и ронял бы /add уже
        # ПОСЛЕ сохранения в БД, попутно съедая рассылку ниже. Уведомление второстепенно.
        try:
            await self._notifier.notify_admins(
                f"✅ Фильм «{saved.title_kk}» добавлен. ID: {saved.id}"
            )
        except Exception:
            logger.exception("Не удалось уведомить админов о фильме #%s", saved.id)
        # Авто-рассылка о новинке (Фаза 12) — в try/except: сбой рассылки НЕ должен
        # отменять добавление фильма (оно уже в БД). Очередь fail-open сама по себе.
        try:
            queued = await self._broadcast.notify_new_movie(saved)
            logger.info("Рассылка о новинке #%s поставлена: %d адресатов", saved.id, queued)
        except Exception:
            logger.exception("Не удалось поставить рассылку о новинке #%s", saved.id)
        return saved
