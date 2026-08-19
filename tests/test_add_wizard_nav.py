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

def test_hero_banner_is_asked_of_every_movie() -> None:
    """Условных шагов больше нет: баннер спрашивают всех (решение 2026-08-19).

    Раньше hero показывался только помеченным «на главную»; теперь hero — это фильм дня,
    в него по очереди попадает весь каталог, и баннер пригодится любому фильму.
    """
    assert _next(AddMovie.poster, {}) is AddMovie.hero
    assert _previous(AddMovie.category, {}) is AddMovie.hero


def test_first_step_has_nowhere_to_go_back() -> None:
    assert _previous(AddMovie.video, {}) is None


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


def test_edit_menu_always_offers_the_hero_banner() -> None:
    """Баннер правится всегда — в т.ч. чтобы добавить его туда, где сначала был /skip."""
    assert f"{EDIT_PREFIX}hero" in _codes(edit_keyboard())


# --- режим точечной правки --------------------------------------------------

async def test_edit_of_one_field_returns_straight_to_summary() -> None:
    state = _state()
    await state.set_state(AddMovie.title_ru)
    await state.update_data(edit=True, title_ru="Шрек")

    await _advance(_TARGET, state)

    assert await state.get_state() == AddMovie.confirm.state
    assert (await state.get_data())["edit"] is False


async def test_skipped_banner_is_distinguishable_from_untouched_step() -> None:
    """«Ещё не спрашивали» и «сознательно пропустил» — разные экраны.

    У первого «Әрі қарай» быть не должно (оставлять нечего), у второго — должна, иначе
    админ, вернувшийся к шагу, не смог бы уйти дальше, не приложив картинку.
    """
    _, untouched = _screen(AddMovie.hero, {})
    text, skipped = _screen(AddMovie.hero, {"hero_file_id": None})

    assert _codes(untouched) == [BACK]
    assert "өткізілген" in text
    assert NEXT in _codes(skipped)


async def test_plain_flow_goes_to_the_next_step() -> None:
    state = _state()
    await state.set_state(AddMovie.title_ru)
    await state.update_data(title_ru="Шрек")

    await _advance(_TARGET, state)

    assert await state.get_state() == AddMovie.title_original.state
