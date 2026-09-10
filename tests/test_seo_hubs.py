"""Тесты справочника хабов (`domain/seo/hubs`): что живёт по `/catalog/<slug>`.

Хабы трёх видов делят одно пространство имён URL, поэтому здесь проверяется не только
разбор слага, но и то, от чего этот разбор молча ломается: пересечение слагов подборок с
категориями и порог, ниже которого год страницы не получает.
"""

from __future__ import annotations

from app.domain.catalog.categories import CATEGORIES
from app.domain.seo.hubs import (
    COLLECTIONS,
    YEAR_MIN_MOVIES,
    HubKind,
    HubOrder,
    indexable_years,
    parse_year,
    resolve_hub,
)

_ENOUGH = YEAR_MIN_MOVIES
_NOT_ENOUGH = YEAR_MIN_MOVIES - 1


# ── пространство имён URL ─────────────────────────────────────────────────────
def test_collection_slugs_never_collide_with_categories() -> None:
    """⚠️ Подборки и разделы живут по одному пути `/catalog/<slug>`.

    Совпадение слагов означало бы, что раздел молча перестал открываться: `resolve_hub`
    отдаёт подборку раньше. Новая категория с именем `new` или `popular` должна ломать
    этот тест, а не прод.
    """
    assert not COLLECTIONS.keys() & CATEGORIES.keys()


def test_collection_slugs_are_not_years() -> None:
    """Слаг подборки, похожий на год, перехватывался бы разбором года."""
    assert all(parse_year(slug) is None for slug in COLLECTIONS)


# ── разбор слага ──────────────────────────────────────────────────────────────
def test_category_slug_resolves_to_category_hub() -> None:
    hub = resolve_hub("kids", year_counts={})

    assert hub is not None
    assert (hub.kind, hub.category, hub.year) == (HubKind.CATEGORY, "kids", None)


def test_collection_slug_resolves_without_filters() -> None:
    """Подборка — весь каталог в другом порядке, поэтому фильтров у неё нет."""
    hub = resolve_hub("popular", year_counts={})

    assert hub is not None
    assert (hub.kind, hub.category, hub.year) == (HubKind.COLLECTION, None, None)
    assert hub.order == HubOrder.POPULAR


def test_new_collection_is_ordered_by_novelty() -> None:
    hub = resolve_hub("new", year_counts={})

    assert hub is not None
    assert hub.order == HubOrder.NEWEST


def test_unknown_slug_has_no_hub() -> None:
    assert resolve_hub("no-such-thing", year_counts={}) is None


def test_hub_path_is_under_catalog() -> None:
    hub = resolve_hub("anime", year_counts={})

    assert hub is not None
    assert hub.path == "/catalog/anime"


# ── годы ──────────────────────────────────────────────────────────────────────
def test_year_slug_resolves_when_there_is_enough_to_show() -> None:
    hub = resolve_hub("2024", year_counts={2024: _ENOUGH})

    assert hub is not None
    assert (hub.kind, hub.year, hub.category) == (HubKind.YEAR, 2024, None)


def test_thin_year_gets_no_page() -> None:
    """Год с парой фильмов — не «мультфильмы 2024 года»: страница была бы пустышкой."""
    assert resolve_hub("2024", year_counts={2024: _NOT_ENOUGH}) is None


def test_year_absent_from_catalog_gets_no_page() -> None:
    assert resolve_hub("1998", year_counts={2024: 50}) is None


def test_year_heading_names_the_year_in_both_languages() -> None:
    hub = resolve_hub("2024", year_counts={2024: _ENOUGH})

    assert hub is not None
    assert "2024" in hub.heading_kk
    assert "2024" in hub.heading_ru


def test_parse_year_wants_exactly_four_digits() -> None:
    """`/catalog/24` — не год: иначе любой короткий числовой слаг стал бы страницей."""
    assert parse_year("2024") == 2024
    assert parse_year("24") is None
    assert parse_year("20245") is None
    assert parse_year("20x4") is None


def test_parse_year_rejects_impossible_years() -> None:
    """Опечатка в визарде не должна заводить страницу несуществующего года."""
    assert parse_year("1799") is None
    assert parse_year("3000") is None


def test_indexable_years_are_newest_first_and_pass_the_threshold() -> None:
    counts = {2020: _ENOUGH, 2024: _ENOUGH, 2022: _NOT_ENOUGH}

    assert indexable_years(counts) == [2024, 2020]


def test_indexable_years_is_empty_without_data() -> None:
    assert indexable_years({}) == []
