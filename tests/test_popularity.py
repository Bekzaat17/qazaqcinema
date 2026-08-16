"""Формула популярности (чистая функция, без БД).

Смысл проверки — не арифметика, а бизнес-правило: просмотр весит больше звёздочки.
Просмотр доступен только подписчику, а звезду ставит кто угодно бесплатно, поэтому при
равных весах избранное задавило бы просмотры и полка «Танымал» превратилась бы в список
желаний. Тест ловит именно этот перекос, если веса когда-нибудь начнут крутить.
"""

from __future__ import annotations

from app.domain.catalog.popularity import FAVORITE_WEIGHT, PLAY_WEIGHT, popularity_score


def test_play_outweighs_a_favorite() -> None:
    assert PLAY_WEIGHT > FAVORITE_WEIGHT
    assert popularity_score(play_count=1, favorites_count=0) > popularity_score(
        play_count=0, favorites_count=1
    )


def test_favorites_still_move_the_needle() -> None:
    """Звёздочки не декоративны: без просмотров они и определяют порядок полки."""
    assert popularity_score(play_count=0, favorites_count=3) > popularity_score(
        play_count=0, favorites_count=2
    )


def test_signals_add_up() -> None:
    assert popularity_score(play_count=2, favorites_count=3) == (
        2 * PLAY_WEIGHT + 3 * FAVORITE_WEIGHT
    )


def test_cold_start_is_zero() -> None:
    """Новый фильм не получает форы — порядок решают rating/новизна в ORDER BY."""
    assert popularity_score(play_count=0, favorites_count=0) == 0
