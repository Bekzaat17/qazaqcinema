"""Навигация визарда `/add`: шаг назад, «оставить как есть», точечная правка полей.

Проверяем ровно то, ради чего порядок шагов вынесен в данные (`_ORDER`): ветку hero
(её нет у не-featured фильма), возврат назад без потери введённого и режим правки —
после правки одного поля визард обязан вернуться к сводке, а не идти по шагам заново.
FSM — настоящий (aiogram + MemoryStorage), отправка сообщений в тестах не нужна:
`_send` умеет работать только с реальным `Message`, с заглушкой он просто молчит.
"""

from __future__ import annotations

from typing import Any, cast

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message
from app.bot.handlers.add_movie import (
    AddMovie,
    _advance,
    _has_value,
    _next,
    _previous,
    _screen,
)
from app.bot.keyboards.add_movie import BACK, EDIT_PREFIX, NEXT, edit_keyboard

_TARGET = cast(Message | CallbackQuery, object())  # заглушка адресата: сообщений не шлём


def _state() -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1)
    )


def _codes(markup: Any) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


# --- порядок шагов ----------------------------------------------------------

def test_only_one_image_is_asked_for() -> None:
    """Картинка у фильма одна — постер (решение 2026-08-19).

    Ни вопроса «показывать на главной?», ни отдельного широкого баннера в визарде нет:
    hero — это фильм дня, туда по очереди попадает весь каталог, а широкую поверхность
    фронт делает из того же постера. Сосед постера — `title_kk` (после него шаг «сериал»
    из решения 2026-08-28 сдвинул порядок: video → category → series → poster → title_kk).
    """
    assert _next(AddMovie.poster, {}) is AddMovie.title_kk
    assert _previous(AddMovie.title_kk, {}) is AddMovie.poster


def test_first_step_has_nowhere_to_go_back() -> None:
    assert _previous(AddMovie.video, {}) is None


# --- сериалы: серия существующего сезона пропускает постер/категорию/названия/описание ---

def test_existing_season_skips_its_own_fields() -> None:
    """Серия УЖЕ СУЩЕСТВУЮЩЕГО сезона (решение 2026-08-28): постер/категории/названия/
    описание несёт сезон, спрашивать их заново незачем — визард перескакивает эти шаги
    и от `series` сразу попадает на `year`."""
    data = {"season_id": 7}
    assert _next(AddMovie.series, data) is AddMovie.year
    assert _previous(AddMovie.year, data) is AddMovie.series


def test_new_season_still_asks_its_own_fields() -> None:
    """А вот НОВЫЙ сезон (даже под существующим сериалом) эти поля собирает как обычно —
    они станут данными сезона (`season_new_number` без `season_id`)."""
    data = {"season_new_number": 3}
    assert _next(AddMovie.series, data) is AddMovie.poster
    assert _next(AddMovie.poster, data) is AddMovie.title_kk


def test_standalone_movie_asks_every_field() -> None:
    """Обычный фильм («Жоқ, жеке фильм») ничего не пропускает."""
    assert _next(AddMovie.series, {}) is AddMovie.poster


# --- экран шага -------------------------------------------------------------

def test_first_screen_has_no_navigation() -> None:
    _, markup = _screen(AddMovie.video, {})
    assert markup is None


def test_filled_step_shows_current_value_and_keep_button() -> None:
    text, markup = _screen(AddMovie.title_ru, {"title_ru": "Шрек"})
    assert "Шрек" in text
    assert _codes(markup) == [BACK, NEXT]


def test_skipped_step_is_marked_and_can_be_refilled() -> None:
    text, markup = _screen(AddMovie.year, {"year": None})
    assert "өткізілген" in text  # видно, что тут нажали /skip — значит есть что поправить
    assert NEXT in _codes(markup)


def test_untouched_step_offers_only_back() -> None:
    _, markup = _screen(AddMovie.title_ru, {})
    assert _codes(markup) == [BACK]


def test_category_step_keeps_selection_but_has_no_keep_button() -> None:
    data = {"categories": ["disney"]}
    assert _has_value(AddMovie.category, data) is False  # роль «дальше» играет «Дайын»
    _, markup = _screen(AddMovie.category, data)
    assert BACK in _codes(markup)


def test_edit_menu_has_no_banner_field() -> None:
    """Править нечего: широкого баннера у фильма больше не бывает."""
    codes = _codes(edit_keyboard())
    assert f"{EDIT_PREFIX}hero" not in codes
    assert f"{EDIT_PREFIX}poster" in codes


# --- режим точечной правки --------------------------------------------------

async def test_edit_of_one_field_returns_straight_to_summary() -> None:
    state = _state()
    await state.set_state(AddMovie.title_ru)
    await state.update_data(edit=True, title_ru="Шрек")

    await _advance(_TARGET, state)

    assert await state.get_state() == AddMovie.confirm.state
    assert (await state.get_data())["edit"] is False


async def test_plain_flow_goes_to_the_next_step() -> None:
    state = _state()
    await state.set_state(AddMovie.title_ru)
    await state.update_data(title_ru="Шрек")

    await _advance(_TARGET, state)

    assert await state.get_state() == AddMovie.title_original.state
