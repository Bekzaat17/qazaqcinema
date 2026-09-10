"""Тесты перелинковки публичных SEO-страниц: ссылки на разделы и `lastmod` хабов.

Зачем это отдельным файлом: до появления разделов на весь сайт приходилась ОДНА хаб-страница,
а карточка фильма была тупиком (единственная ссылка вела назад в каталог). Проверяем именно
структуру связей.

Счётчики разделов роутер получает готовыми (один `GROUP BY` в БД → каноничный порядок в
`CatalogService.category_counts`), поэтому здесь проверяется только то, что делает сам
роутер: строит путь и не ведёт туда, где страницы нет. Подбор похожих ушёл в SQL — он
проверяется на живой базе (`test_repositories`).
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.routers.public_seo import _category_links, _newest
from app.domain.entities.movie import Movie


def _dated(movie_id: int, created_at: datetime | None) -> Movie:
    movie = _movie(movie_id, ["disney"])
    movie.created_at = created_at
    return movie


def _movie(movie_id: int, categories: list[str], title: str = "Фильм") -> Movie:
    return Movie(
        title_kk=title,
        description="",
        categories=categories,
        poster_url=f"/posters/{movie_id}.jpg",
        telegram_file_id="FILEID",
        id=movie_id,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


# ── навигация по разделам ─────────────────────────────────────────────────────
def test_category_link_path_points_to_landing_page() -> None:
    (link,) = _category_links([("fairytale", 3)])

    assert link.path == "/catalog/fairytale"
    assert link.count == 3
    assert link.category.title_kk == "Ертегілер"


def test_category_links_keep_the_order_they_came_in() -> None:
    """Каноничный порядок задаёт справочник (в сервисе) — роутер его не переставляет."""
    links = _category_links([("disney", 2), ("anime", 1), ("kids", 1)])

    assert [link.category.slug for link in links] == ["disney", "anime", "kids"]


def test_category_links_ignore_unknown_slug() -> None:
    """Категория, которой нет в справочнике, ссылки не получает — её некуда вести."""
    links = _category_links([("disney", 1), ("no-such-category", 5)])

    assert [link.category.slug for link in links] == ["disney"]


def test_category_links_are_empty_without_counts() -> None:
    """Пустых разделов в счётчиках не бывает: их отдаёт `GROUP BY` по живым строкам."""
    assert _category_links([]) == []


# ── lastmod страниц-хабов ─────────────────────────────────────────────────────
def test_newest_picks_latest_creation_date() -> None:
    """Хаб «изменился» тогда, когда в нём появился новый фильм."""
    movies = [
        _dated(1, datetime(2026, 7, 1, tzinfo=UTC)),
        _dated(2, datetime(2026, 8, 14, tzinfo=UTC)),
        _dated(3, datetime(2026, 8, 2, tzinfo=UTC)),
    ]

    assert _newest(movies) == "2026-08-14"


def test_newest_is_none_for_empty_set() -> None:
    """Без даты `_url_entry` просто не пишет <lastmod> — пустой тег был бы невалиден."""
    assert _newest([]) is None


def test_newest_ignores_movies_without_date() -> None:
    """created_at проставляет БД; до вставки он None и датой хаба быть не может."""
    movies = [_dated(1, None), _dated(2, datetime(2026, 8, 5, tzinfo=UTC))]

    assert _newest(movies) == "2026-08-05"


def test_newest_is_none_when_no_movie_has_date() -> None:
    assert _newest([_dated(1, None)]) is None
