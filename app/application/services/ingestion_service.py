"""Добавление фильма в каталог. Источник — бот-визард `/add` (FSM).

Сервис чист: знает только порты (репозиторий, хранилище постеров, обработчик картинок,
нотификатор), ничего про aiogram. Видео уже лежит в канале-архиве (его file_id приходит
готовым); постер приходит байтами, нормализуется через `ImageProcessor` и уходит в
`PosterStorage` (статика на VPS).
"""

from __future__ import annotations

import logging
from html import escape

from app.application.ports.catalog_cache import CatalogCache
from app.application.ports.images import POSTER, ImageProcessor
from app.application.ports.repositories import MovieRepository, SeasonRepository
from app.application.ports.storage import PosterStorage
from app.application.ports.telegram import TelegramNotifier
from app.application.services.broadcast_service import BroadcastService
from app.domain.entities.movie import Movie

logger = logging.getLogger(__name__)


class MovieIngestionService:
    def __init__(
        self,
        movies: MovieRepository,
        seasons: SeasonRepository,
        notifier: TelegramNotifier,
        posters: PosterStorage,
        images: ImageProcessor,
        catalog_cache: CatalogCache,
        broadcast: BroadcastService,
    ) -> None:
        self._movies = movies
        self._seasons = seasons
        self._notifier = notifier
        self._posters = posters
        self._images = images
        self._cache = catalog_cache
        self._broadcast = broadcast

    async def ingest(
        self,
        *,
        title_kk: str | None = None,
        title_ru: str | None = None,
        title_original: str | None = None,
        categories: list[str] | None = None,
        description: str | None = None,
        year: int | None,
        rating: float | None,
        notify: bool,
        video_file_id: str,
        poster_bytes: bytes | None = None,
        season_id: int | None = None,
    ) -> Movie:
        """Нормализовать/сохранить постер (+ hero-баннер), записать фильм, уведомить админов.

        `video_file_id` — file_id видео в канале-архиве (отдаётся ТОЛЬКО боту).

        Два режима (решение 2026-08-28, сериалы):
        • `season_id=None` — самостоятельный фильм: `title_kk`/`categories`/`description`/
          `poster_bytes` ОБЯЗАТЕЛЬНЫ, постер нормализуется к 2:3 и сохраняется здесь же.
        • `season_id` задан — серия сезона: постер/название/категории/описание берутся с
          сезона (не спрашиваются заново на визарде), номер серии — следующий по счёту в
          сезоне, а `title_kk`, если не передан явно, — «<название сезона> — N-бөлім».
          `poster_bytes` в этом режиме не используется (сезон уже хранит свой постер).

        Картинка у фильма/сезона одна: широкий баннер больше не запрашивается (решение
        2026-08-19) — hero строит фон из этого же постера. Битую картинку
        `ImageProcessor` отклонит (ValueError).

        `notify` — рассылать ли новинку. Решение принимает админ на каждом фильме (шаг
        визарда), а не код: каталог заливают пачками по десятку-другому за вечер, и
        безусловная рассылка превращала это в десятки пушей за день каждому подписчику —
        верный путь в блок. Кому именно уйдёт, решает не этот флаг, а тумблер в профиле
        (`BroadcastService.notify_new_movie` берёт только согласившихся).
        """
        episode_number: int | None = None
        if season_id is not None:
            season = await self._seasons.get(season_id)
            if season is None:
                raise ValueError(f"Сезон #{season_id} не найден")
            poster_url = season.poster_url
            categories = categories if categories is not None else season.categories
            description = description if description is not None else season.description
            episode_number = len(await self._movies.list_by_season(season_id)) + 1
            title_kk = title_kk or f"{season.title_kk} — {episode_number}-бөлім"
        else:
            if (
                title_kk is None
                or description is None
                or categories is None
                or poster_bytes is None
            ):
                raise ValueError(
                    "Жеке фильмге title_kk/categories/description/poster_bytes міндетті"
                )
            normalized = await self._images.normalize(poster_bytes, POSTER)
            poster_url = await self._posters.save(normalized)

        movie = Movie(
            title_kk=title_kk,
            title_ru=title_ru,
            title_original=title_original,
            categories=categories,
            description=description,
            poster_url=poster_url,
            telegram_file_id=video_file_id,
            year=year,
            rating=rating,
            season_id=season_id,
            episode_number=episode_number,
        )
        saved = await self._movies.add(movie)
        # Сбрасываем ВЕСЬ кэш каталога (главная/чипы/страницы браузинга), иначе новинка не
        # видна до истечения TTL (Фаза 11.2/13; invalidate чистит весь namespace catalog:*).
        await self._cache.invalidate()
        # Тоже в try/except: notify_admins шлёт КАЖДОМУ из BOT_ADMIN_USER_IDS, а админ,
        # не нажавший /start (или заблокировавший бота), даёт 403 — и ронял бы /add уже
        # ПОСЛЕ сохранения в БД, попутно съедая рассылку ниже. Уведомление второстепенно.
        try:
            # Название экранируем: notify_admins шлёт HTML (см. порт).
            await self._notifier.notify_admins(
                f"✅ Фильм «{escape(saved.title_kk)}» добавлен. ID: {saved.id}"
            )
        except Exception:
            logger.exception("Не удалось уведомить админов о фильме #%s", saved.id)
        # Рассылка о новинке (Фаза 12) — в try/except: сбой рассылки НЕ должен
        # отменять добавление фильма (оно уже в БД). Очередь fail-open сама по себе.
        if not notify:
            return saved
        try:
            queued = await self._broadcast.notify_new_movie(saved)
            logger.info("Рассылка о новинке #%s поставлена: %d адресатов", saved.id, queued)
        except Exception:
            logger.exception("Не удалось поставить рассылку о новинке #%s", saved.id)
        return saved
