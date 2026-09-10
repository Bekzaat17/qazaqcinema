"""Локальное хранилище постеров на диске VPS (реализует PosterStorage).

Каждый постер лежит в двух копиях: `<uuid>.jpg` (крупная) и `<uuid>_sm.webp` (мелкая,
для сеток и полок). Пишутся только вместе — см. `save`.

Постеры — публичная витрина (их видят и неподписчики), крошечные и нужны под
стабильный URL в `<img>`, поэтому отдаются статикой (Caddy/StaticFiles), а не
прокси-эндпоинтом через бота. Имя файла — uuid (без перечислимости и коллизий).
"""

from __future__ import annotations

import asyncio
from pathlib import Path, PurePosixPath
from uuid import uuid4

from app.application.ports.storage import thumb_url
from app.config.settings import MediaConfig

# Подкаталог постеров — И на диске (`<media.root>/posters`), И в публичном URL. Одно
# место: из него же собирается путь для отправки файлом (`local_path`).
_SUBDIR = "posters"


class LocalPosterStorage:
    def __init__(self, media: MediaConfig) -> None:
        self._dir = Path(media.root) / _SUBDIR
        self._url_base = media.posters_url_base.rstrip("/")

    async def save(self, data: bytes, *, thumb: bytes) -> str:
        # Постер уже нормализован в JPEG (ImageProcessor) → расширение фиксировано, в имя
        # не подставляем внешних строк (никакой path-инъекции); uuid — без перечислимости.
        name = f"{uuid4().hex}.jpg"
        # Мелкая копия ПЕРВОЙ: если диск кончится на ней, крупной ещё нет, а значит нет и
        # URL в БД — фильм просто не заведётся. Обратный порядок оставил бы в каталоге
        # карточку, у которой мелкой копии не существует.
        await asyncio.to_thread(self._write, self._dir / thumb_url(name), thumb)
        await asyncio.to_thread(self._write, self._dir / name, data)
        return f"{self._url_base}/{name}"

    def local_path(self, poster_url: str) -> str | None:
        """`/posters/<uuid>.jpg` → `posters/<uuid>.jpg` (относительно медиа-корня)."""
        name = PurePosixPath(poster_url).name
        if not name or not (self._dir / name).is_file():
            return None
        return f"{_SUBDIR}/{name}"

    @staticmethod
    def _write(dest: Path, data: bytes) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
