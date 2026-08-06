"""Выбор фильма для hero главной — чистая функция (данные внутрь, фильм наружу).

Правило (решение 2026-08-06): свежий баннер держится на главной закреплённым
`PIN_DAYS` суток — иначе только что добавленная новинка мелькнула бы на hero пару
часов и утонула. Дальше главная «дышит»: каждый день на hero встаёт другой фильм
ИЗ ТЕХ, У КОГО ЕСТЬ горизонтальный баннер (`hero_image_url`) — без баннера hero
растянул бы вертикальный постер.

Выбор дня **детерминированный**, а не `random.choice` на каждый запрос: главная
кэшируется (`catalog:home`) и её видят все сразу — случайность «на запрос» давала бы
разным юзерам разный hero, а F5 менял бы картинку под рукой. Здесь один и тот же день
всегда даёт один и тот же фильм.

Перестановка на круг (`Random(cycle).shuffle`), а не выбор наугад: внутри круга длиной
в число баннеров фильмы не повторяются — порядок выглядит случайным, но «три дня подряд
один и тот же» невозможно. Граница суток — UTC (в Казахстане это ~05:00, тихое время:
hero не подменяется под вечерним трафиком).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from random import Random

from app.domain.entities.movie import Movie

# Сколько суток свежий баннер висит на hero без ротации (данные — крутить здесь).
PIN_DAYS = 3


def pick_hero(pinned: Movie | None, rotation: list[Movie], now: datetime) -> Movie | None:
    """Кого показать на hero сейчас: свежий закреплённый или «фильм дня» из ротации.

    `pinned` — выбор репозитория (свежайший featured), `rotation` — все фильмы с
    горизонтальным баннером. Ротация пуста → остаёмся на `pinned` (главная не пустеет).
    """
    if _is_pinned_fresh(pinned, now):
        return pinned
    if not rotation:
        return pinned
    return _hero_of_the_day(rotation, now)


def _is_pinned_fresh(movie: Movie | None, now: datetime) -> bool:
    """Баннер моложе PIN_DAYS? Без даты добавления считаем «не свежий» → в ротацию."""
    if movie is None or movie.created_at is None:
        return False
    created = movie.created_at
    if created.tzinfo is None:
        # Из БД дата приходит с зоной; страховка от наивной даты (тесты/фикстуры),
        # иначе вычитание aware-naive упало бы TypeError прямо на главной.
        created = created.replace(tzinfo=now.tzinfo)
    return now - created < timedelta(days=PIN_DAYS)


def _hero_of_the_day(rotation: list[Movie], now: datetime) -> Movie:
    """Детерминированный фильм дня: перестановка круга по номеру круга + позиция в нём."""
    ordered = sorted(rotation, key=lambda movie: movie.id or 0)
    day = now.date().toordinal()
    cycle, position = divmod(day, len(ordered))
    shuffled = list(ordered)
    Random(cycle).shuffle(shuffled)
    return shuffled[position]
