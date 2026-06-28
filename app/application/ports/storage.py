"""Порт хранилища постеров (DIP).

Сервис сохраняет байты картинки и получает публичный URL, не зная, где она лежит
(диск VPS, S3, R2). Текущая реализация — `infrastructure/storage/local.py`.
"""

from __future__ import annotations

from typing import Protocol


class PosterStorage(Protocol):
    async def save(self, data: bytes, ext: str = "jpg") -> str:
        """Сохранить постер; вернуть публичный URL/путь (идёт в `MovieOut.poster_url`)."""
        ...
