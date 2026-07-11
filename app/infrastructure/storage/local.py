"""Локальное хранилище постеров на диске VPS (реализует PosterStorage).

Постеры — публичная витрина (их видят и неподписчики), крошечные и нужны под
стабильный URL в `<img>`, поэтому отдаются статикой (Caddy/StaticFiles), а не
прокси-эндпоинтом через бота. Имя файла — uuid (без перечислимости и коллизий).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

from app.config.settings import MediaConfig


class LocalPosterStorage:
    def __init__(self, media: MediaConfig) -> None:
        self._dir = Path(media.root) / "posters"
        self._url_base = media.posters_url_base.rstrip("/")

    async def save(self, data: bytes) -> str:
        # Постер уже нормализован в JPEG (ImageProcessor) → расширение фиксировано, в имя
        # не подставляем внешних строк (никакой path-инъекции); uuid — без перечислимости.
        name = f"{uuid4().hex}.jpg"
        await asyncio.to_thread(self._write, self._dir / name, data)
        return f"{self._url_base}/{name}"

    @staticmethod
    def _write(dest: Path, data: bytes) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
