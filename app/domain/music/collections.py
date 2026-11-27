"""Готовые плейлисты: собираются из каталога сами, админу ничего вести не нужно.

Справочник подборок — данные (подпись, размер); КАК подборка собирается — код по
`CollectionKind` в `MusicCatalogService`: новое правило отбора меняет поведение, а не
подпись, поэтому это энум, а не строка справочника.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CollectionKind(StrEnum):
    WEEK_HITS = "week_hits"  # больше всего РАЗНЫХ слушателей за 7 дней
    NEW = "new"              # последние добавленные слушателями
    BEST = "best"            # больше всего сохранений и прослушиваний за всё время


@dataclass(frozen=True, slots=True)
class Collection:
    kind: CollectionKind
    title: str
    subtitle: str
    size: int


COLLECTIONS: tuple[Collection, ...] = (
    Collection(CollectionKind.WEEK_HITS, "Аптаның хиттері", "Осы аптада ең көп тыңдалғандар", 30),
    Collection(CollectionKind.NEW, "Жаңа әндер", "Тыңдаушылар соңғы қосқандар", 30),
    Collection(CollectionKind.BEST, "Үздіктер", "Ең көп сақталған әндер", 50),
)


def get_collection(key: str) -> Collection | None:
    return next((c for c in COLLECTIONS if c.kind.value == key), None)
