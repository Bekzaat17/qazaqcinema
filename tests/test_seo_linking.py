"""Тесты перелинковки публичных SEO-страниц: разделы каталога и блок «похожих».

Зачем это отдельным файлом: до появления разделов на весь сайт приходилась ОДНА хаб-страница,
а карточка фильма была тупиком (единственная ссылка вела назад в каталог). Проверяем именно
структуру связей — что раздел собирается только из непустых категорий и что похожие
подбираются по общим категориям, а не наугад.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.routers.public_seo import _category_links, _newest, _related
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
def test_category_links_counts_each_category_of_a_movie() -> None:
    """Фильм мультикатегорийный — он даёт +1 КАЖДОЙ своей категории."""
    movies = [
        _movie(1, ["disney", "kids"]),
        _movie(2, ["disney"]),
        _movie(3, ["anime"]),
    ]

    counts = {link.category.slug: link.count for link in _category_links(movies)}

    assert counts == {"disney": 2, "anime": 1, "kids": 1}


def test_category_links_skip_empty_categories() -> None:
    """В навигацию (и в sitemap) идут только непустые разделы: пустой отдаёт 404."""
    links = _category_links([_movie(1, ["anime"])])

    assert [link.category.slug for link in links] == ["anime"]


def test_category_links_follow_reference_order_not_alphabet() -> None:
    """Порядок — каноничный из справочника (тип → происхождение → аудитория → жанр)."""
    movies = [_movie(1, ["comedy", "kids", "disney", "anime"])]

    assert [link.category.slug for link in _category_links(movies)] == [
        "disney",
        "anime",
        "kids",
        "comedy",
    ]


def test_category_links_ignore_unknown_slug() -> None:
    """Категория, которой нет в справочнике, страницы не получает — её некуда вести."""
    links = _category_links([_movie(1, ["disney", "no-such-category"])])

    assert [link.category.slug for link in links] == ["disney"]


def test_category_link_path_points_to_landing_page() -> None:
    (link,) = _category_links([_movie(1, ["fairytale"])])

    assert link.path == "/catalog/fairytale"


# ── блок «Ұқсас фильмдер» ─────────────────────────────────────────────────────
def test_related_prefers_more_shared_categories() -> None:
    current = _movie(1, ["disney", "kids"])
    movies = [
        current,
        _movie(2, ["disney"]),           # 1 общая
        _movie(3, ["disney", "kids"]),   # 2 общие → выше
        _movie(4, ["anime"]),            # ни одной → не попадёт
    ]

    assert [m.id for m in _related(movies, current)] == [3, 2]


def test_related_excludes_the_movie_itself() -> None:
    current = _movie(1, ["disney"])

    assert current not in _related([current, _movie(2, ["disney"])], current)


def test_related_is_empty_for_movie_without_categories() -> None:
    current = _movie(1, [])

    assert _related([current, _movie(2, ["disney"])], current) == []


def test_related_is_capped() -> None:
    """Подвал карточки — перелинковка, а не второй каталог: ссылок ограниченное число."""
    current = _movie(1, ["disney"])
    movies = [current] + [_movie(i, ["disney"]) for i in range(2, 30)]

    assert len(_related(movies, current)) == 6


def test_related_order_is_deterministic() -> None:
    """Страница кэшируется и отдаётся всем одинаковой — случайности в подборе быть не должно."""
    current = _movie(1, ["disney"])
    movies = [current, _movie(2, ["disney"]), _movie(3, ["disney"])]

    assert _related(movies, current) == _related(movies, current)


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
