"""Клавиатуры визарда /add: навигация (назад/оставить), категории, подтверждение, правка полей."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.catalog.categories import all_categories

CATEGORY_PREFIX = "addcat:"
CATEGORY_DONE = "addcat:__done__"
FEATURED_PREFIX = "addfeat:"
CONFIRM = "addmovie:confirm"
CANCEL = "addmovie:cancel"
BACK = "addmovie:back"
NEXT = "addmovie:next"
EDIT = "addmovie:edit"
EDIT_PREFIX = "addedit:"
EDIT_BACK = "addedit:__back__"

_BACK_TEXT = "⬅️ Артқа"
_NEXT_TEXT = "➡️ Әрі қарай"

# Поля, доступные для точечной правки со сводки. Значение — имя шага (State) визарда,
# поэтому меню правки и сам визард всегда согласованы: новый шаг = +1 строка тут.
EDIT_FIELDS: tuple[tuple[str, str], ...] = (
    ("video", "🎬 Видео"),
    ("poster", "🖼 Постер"),
    ("featured", "📌 Басты бет"),
    ("hero", "⭐ Hero-баннер"),
    ("category", "🗂 Категориялар"),
    ("title_kk", "🇰🇿 Атауы (KK)"),
    ("title_ru", "🇷🇺 Атауы (RU)"),
    ("title_original", "🌐 Ориг. атауы"),
    ("year", "📅 Жыл"),
    ("rating", "⭐ Рейтинг"),
    ("description", "📝 Сипаттама"),
)


def _nav_row(*, back: bool, forward: bool) -> list[InlineKeyboardButton]:
    """Строка навигации визарда: шаг назад и «оставить как есть» (если есть что оставлять)."""
    row: list[InlineKeyboardButton] = []
    if back:
        row.append(InlineKeyboardButton(text=_BACK_TEXT, callback_data=BACK))
    if forward:
        row.append(InlineKeyboardButton(text=_NEXT_TEXT, callback_data=NEXT))
    return row


def _with_nav(
    rows: list[list[InlineKeyboardButton]], *, back: bool, forward: bool = False
) -> InlineKeyboardMarkup:
    nav = _nav_row(back=back, forward=forward)
    return InlineKeyboardMarkup(inline_keyboard=[*rows, nav] if nav else rows)


def step_keyboard(*, back: bool, forward: bool) -> InlineKeyboardMarkup | None:
    """Шаг без своих кнопок (ввод текста/фото) — только навигация; на первом шаге её нет."""
    if not back and not forward:
        return None
    return _with_nav([], back=back, forward=forward)


def featured_keyboard(*, back: bool = True, forward: bool = False) -> InlineKeyboardMarkup:
    """«На главную (hero)?» — Иә/Жоқ. Иә → админ пришлёт широкий/квадратный hero-баннер."""
    return _with_nav(
        [
            [
                InlineKeyboardButton(text="⭐ Иә", callback_data=f"{FEATURED_PREFIX}1"),
                InlineKeyboardButton(text="Жоқ", callback_data=f"{FEATURED_PREFIX}0"),
            ]
        ],
        back=back,
        forward=forward,
    )


def category_keyboard(
    selected: set[str] | None = None, *, back: bool = True
) -> InlineKeyboardMarkup:
    """Мультивыбор категорий (чекбоксы): фильм может быть fantasy + мультфильм + …

    Каждая кнопка — тумблер: нажатие добавляет/снимает категорию, выбранные помечены
    «✅». Внизу — «Дайын» (готово), которая уводит дальше по визарду (нужна ≥1 категория).
    Данные → UI: новая категория = +1 запись в справочнике. По 2 в ряд (категорий ~20).
    """
    selected = selected or set()
    buttons = [
        InlineKeyboardButton(
            text=("✅ " if category.slug in selected else "") + category.title_ru,
            callback_data=f"{CATEGORY_PREFIX}{category.slug}",
        )
        for category in all_categories()
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="➡️ Дайын", callback_data=CATEGORY_DONE)])
    return _with_nav(rows, back=back)


def confirm_keyboard() -> InlineKeyboardMarkup:
    """Сводка: сохранить / поправить одно поле / отменить (+ шаг назад к описанию)."""
    return _with_nav(
        [
            [
                InlineKeyboardButton(text="✅ Сақтау", callback_data=CONFIRM),
                InlineKeyboardButton(text="✏️ Түзету", callback_data=EDIT),
            ],
            [InlineKeyboardButton(text="❌ Болдырмау", callback_data=CANCEL)],
        ],
        back=True,
    )


def edit_keyboard(*, is_featured: bool) -> InlineKeyboardMarkup:
    """Меню правки: прыжок к одному полю (после ввода — сразу обратно к сводке).

    Hero-баннер показываем только у featured-фильма: у остальных его просто нет.
    """
    buttons = [
        InlineKeyboardButton(text=title, callback_data=f"{EDIT_PREFIX}{field}")
        for field, title in EDIT_FIELDS
        if field != "hero" or is_featured
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text=_BACK_TEXT, callback_data=EDIT_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
