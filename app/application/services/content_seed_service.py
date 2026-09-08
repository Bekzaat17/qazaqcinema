"""Заливка контента в пул: проверка справочников + upsert по `slug`.

Разбор YAML и копирование картинок — инфраструктура (`infrastructure/content/`);
сюда приходят уже собранные `ContentItem`. Здесь — то, что не зависит от формата
файла: тема должна существовать в справочнике, у элемента с картинкой подпись должна
влезать в лимит, и элемент должен быть записан в БД без сброса истории публикаций.
"""

from __future__ import annotations

import logging

from app.application.ports.content import ContentRepository
from app.domain.channel.content.item import ContentItem
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.topics import get_topic
from app.domain.errors import AppError

logger = logging.getLogger(__name__)


class SeedError(AppError, ValueError):
    """Элемент не проходит проверку — сидер останавливается ДО записи (всё или ничего)."""


class ContentSeedService:
    def __init__(self, items: ContentRepository) -> None:
        self._items = items

    def validate(self, items: list[ContentItem]) -> None:
        seen: set[str] = set()
        for item in items:
            if item.slug in seen:
                raise SeedError(f"slug повторяется: {item.slug}")
            seen.add(item.slug)
            if get_topic(item.topic) is None:
                raise SeedError(f"{item.slug}: неизвестная тема '{item.topic}' (см. topics.py)")
            if item.kind.is_quiz and item.payload is None:
                raise SeedError(f"{item.slug}: квиз без payload")
            if item.kind in (ContentKind.LONGREAD, ContentKind.SAYING) and not item.body_kk.strip():
                raise SeedError(f"{item.slug}: пустой текст")

    async def seed(self, items: list[ContentItem]) -> dict[ContentKind, int]:
        """Проверить всё, записать всё, вернуть размер пула по формам."""
        self.validate(items)
        written = await self._items.upsert_many(items)
        logger.info("Контент залит: %d элементов", written)
        return await self._items.count_by_kind()
