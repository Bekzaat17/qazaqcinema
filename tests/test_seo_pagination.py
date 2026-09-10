"""Тесты правил пагинации SEO-страниц (`domain/seo/pagination`).

Здесь проверяется не вид подвала, а то, от чего зависит индексация: что вторая страница
канонична сама себе, что первая живёт по чистому URL и что крайние номера из навигации
не исчезают. Ошибка в любом из трёх пунктов молча выбрасывает часть каталога из поиска —
поэтому каждый оформлен отдельным тестом.
"""

from __future__ import annotations

import pytest
from app.domain.seo.pagination import Pagination, page_count, paginate


def _pager(page: int, pages: int, path: str = "/catalog") -> Pagination:
    return Pagination(path=path, page=page, pages=pages)


# ── сколько страниц ───────────────────────────────────────────────────────────
def test_page_count_rounds_up() -> None:
    """Остаток — это ещё одна страница, а не «почти страница»."""
    assert page_count(49, 48) == 2
    assert page_count(96, 48) == 2
    assert page_count(97, 48) == 3


def test_empty_list_still_has_one_page() -> None:
    """Пустой каталог отдаёт 200 с пустой сеткой, а не 404: страница-хаб существует."""
    assert page_count(0, 48) == 1


def test_page_size_must_be_positive() -> None:
    with pytest.raises(ValueError):
        page_count(10, 0)


def test_paginate_builds_pager_for_a_ready_slice() -> None:
    pager = paginate(path="/catalog/kids", page=2, total=100, size=48)

    assert (pager.path, pager.page, pager.pages) == ("/catalog/kids", 2, 3)


# ── URL страниц ───────────────────────────────────────────────────────────────
def test_first_page_url_has_no_query_parameter() -> None:
    """`?page=1` — тот же документ по второму адресу, то есть дубль."""
    assert _pager(1, 5).url(1) == "/catalog"


def test_other_pages_carry_the_page_parameter() -> None:
    assert _pager(1, 5).url(3) == "/catalog?page=3"


def test_prev_of_the_second_page_is_the_clean_url() -> None:
    assert _pager(2, 5).prev_url == "/catalog"


def test_edges_have_no_neighbour_link() -> None:
    assert _pager(1, 5).prev_url is None
    assert _pager(5, 5).next_url is None


def test_single_page_shows_no_navigation() -> None:
    assert _pager(1, 1).has_pages is False


# ── canonical и title ─────────────────────────────────────────────────────────
def test_page_two_is_canonical_to_itself() -> None:
    """⚠️ canonical второй страницы на первую выбрасывает из индекса её фильмы."""
    assert _pager(2, 4).canonical_suffix == "?page=2"


def test_first_page_canonical_stays_clean() -> None:
    assert _pager(1, 4).canonical_suffix == ""


def test_pages_get_distinct_titles() -> None:
    """Один заголовок на все страницы — это дубли в выдаче."""
    assert _pager(1, 4).title_suffix == ""
    assert _pager(3, 4).title_suffix == " — 3-бет"


# ── номера в подвале ──────────────────────────────────────────────────────────
def test_short_list_shows_every_number() -> None:
    assert _pager(1, 4).numbers == [1, 2, 3, 4]


def test_long_list_keeps_both_edges_and_the_neighbourhood() -> None:
    """Первая и последняя остаются видимыми: с них начинается и ими кончается обход."""
    assert _pager(10, 21).numbers == [1, None, 8, 9, 10, 11, 12, None, 21]


def test_gap_appears_only_where_numbers_are_skipped() -> None:
    """Рядом с началом разрыва слева нет — иначе «…» врал бы про пропущенную страницу."""
    assert _pager(2, 21).numbers == [1, 2, 3, 4, None, 21]


def test_last_page_neighbourhood_touches_the_end() -> None:
    assert _pager(21, 21).numbers == [1, None, 19, 20, 21]
