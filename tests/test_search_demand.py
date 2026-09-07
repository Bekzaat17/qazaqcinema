"""Спрос словами: нормализация запроса (домен) + запись факта (сервис).

Без БД: `normalize_query` — чистая функция, `register_search` проверяется на фейке
репозитория. Смысл этих тестов не в «работает ли запись», а в двух правилах, из-за
которых таблица вообще имеет ценность: разные написания одного спроса должны
СЛИВАТЬСЯ (иначе топ рассыпется на варианты регистра), а огрызки — не попадать
в статистику вообще.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.application.services.activity_service import UserActivityService
from app.domain.analytics.search import MAX_QUERY_LEN, normalize_query
from app.domain.entities.user import User

from tests.fakes import FakeEvents, FakeSearches

_NOW = datetime(2026, 9, 7, tzinfo=UTC)


class _FakeUsers:
    """`UserRepository` в объёме, который нужен `UserActivityService` для поиска (ничего)."""

    def __init__(self) -> None:
        self.store: dict[int, User] = {}

    async def get(self, telegram_id: int) -> User | None:
        return self.store.get(telegram_id)

    async def upsert(self, user: User) -> User:
        self.store[user.telegram_id] = user
        return user

    async def set_bot_started(self, telegram_id: int, at: datetime | None) -> None:
        return None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Кунг фу панда", "кунг фу панда"),
        # Регистр и лишние пробелы — это одно и то же желание, и в топе они обязаны
        # сложиться в одну строку, а не занять три соседние.
        ("КУНГ   ФУ  панда", "кунг фу панда"),
        ("  Кунг фу панда  ", "кунг фу панда"),
        # Казахские буквы: casefold, а не lower — ради корректности на не-ASCII.
        ("ҚҰМ", "құм"),
        ("Шрек", "шрек"),
    ],
)
def test_normalize_merges_writing_variants(raw: str, expected: str) -> None:
    assert normalize_query(raw) == expected


@pytest.mark.parametrize("raw", ["", " ", "к", "  к  ", "\n"])
def test_normalize_drops_too_short(raw: str) -> None:
    """Спроса в одной букве нет: по такому каталог не ищут, писать в статистику нечего."""
    assert normalize_query(raw) == ""


def test_normalize_truncates_to_column_width() -> None:
    """Длинный запрос обрезаем, а не отбрасываем: это всё равно спрос."""
    normalized = normalize_query("а" * (MAX_QUERY_LEN + 50))
    assert len(normalized) == MAX_QUERY_LEN


async def test_register_search_stores_normalized_query() -> None:
    searches = FakeSearches()
    service = UserActivityService(_FakeUsers(), FakeEvents(), searches)

    await service.register_search(42, "  КУНГ   ФУ панда ", found=3)

    assert searches.added == [(42, "кунг фу панда", 3)]


async def test_register_search_skips_too_short() -> None:
    """Отсев — до репозитория: в таблице не должно быть строк, которые придётся фильтровать."""
    searches = FakeSearches()
    service = UserActivityService(_FakeUsers(), FakeEvents(), searches)

    await service.register_search(42, "к", found=0)

    assert searches.added == []


async def test_missing_queries_are_the_production_queue() -> None:
    """Главный сценарий таблицы: `found = 0` собирается в очередь на озвучку.

    Сортировка — по частоте, затем по числу РАЗНЫХ людей: один упорный посетитель,
    перебирающий написания, не должен обгонять запрос, который спросили несколько
    человек, — иначе очередь заполнялась бы чужим упорством, а не спросом.
    """
    searches = FakeSearches()
    service = UserActivityService(_FakeUsers(), FakeEvents(), searches)

    # «Гарри Поттер» спросили трое разных, «Наруто» — один человек трижды.
    for user_id in (1, 2, 3):
        await service.register_search(user_id, "гарри поттер", found=0)
    for _ in range(3):
        await service.register_search(9, "наруто", found=0)
    # Найденное в очередь не попадает — оно уже залито.
    await service.register_search(4, "шрек", found=2)

    queue = await searches.top_missing(_NOW, _NOW, limit=10)

    assert [d.query for d in queue] == ["гарри поттер", "наруто"]
    assert queue[0].hits == 3 and queue[0].people == 3
    assert queue[1].hits == 3 and queue[1].people == 1
    assert await searches.count_missing(_NOW, _NOW) == 6
    assert await searches.count(_NOW, _NOW) == 7
