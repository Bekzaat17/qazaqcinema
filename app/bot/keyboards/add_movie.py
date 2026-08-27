"""Клавиатуры визарда /add: навигация (назад/оставить), категории, подтверждение, правка полей."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.catalog.categories import all_categories
from app.domain.entities.season import Season
from app.domain.entities.series import Series

CATEGORY_PREFIX = "addcat:"
CATEGORY_DONE = "addcat:__done__"
NOTIFY_PREFIX = "addnotify:"
CONFIRM = "addmovie:confirm"
CANCEL = "addmovie:cancel"
BACK = "addmovie:back"
NEXT = "addmovie:next"
EDIT = "addmovie:edit"
EDIT_PREFIX = "addedit:"
EDIT_BACK = "addedit:__back__"

# Сериалы (решение 2026-08-28): корневой экран шага «серия» — 3 варианта, дальше по
# нажатию либо список сериалов, либо список сезонов внутри выбранного.
SERIES_LIST = "addseries:list"
SERIES_NEW = "addseries:new"
SERIES_NONE = "addseries:none"
SERIES_MENU = "addseries:menu"  # назад к корневым 3 кнопкам из списка сериалов
SERIES_PICK_PREFIX = "addseries:pick:"
SEASON_NEW = "addseason:new"
SEASON_PICK_PREFIX = "addseason:pick:"

_BACK_TEXT = "⬅️ Артқа"
_NEXT_TEXT = "➡️ Әрі қарай"

# Поля, доступные для точечной правки со сводки. Значение — имя шага (State) визарда,
# поэтому меню правки и сам визард всегда согласованы: новый шаг = +1 строка тут.
# Поля постер/категория/названия/описание жмутся тут же, но при серии существующего
# сезона (season_id уже выбран) они не применимы — `edit_keyboard` их фильтрует.
EDIT_FIELDS: tuple[tuple[str, str], ...] = (
    ("video", "🎬 Видео"),
    ("series", "📺 Сериал"),
    ("poster", "🖼 Постер"),
    ("category", "🗂 Категориялар"),
    ("title_kk", "🇰🇿 Атауы (KK)"),
    ("title_ru", "🇷🇺 Атауы (RU)"),
    ("title_original", "🌐 Ориг. атауы"),
    ("year", "📅 Жыл"),
    ("rating", "⭐ Рейтинг"),
    ("description", "📝 Сипаттама"),
    ("notify", "🔔 Хабарлама"),
)
# Из них скрываем при серии существующего сезона — сезон уже несёт своё название/
# категории/описание/постер, спрашивать их заново на каждую серию незачем.
_SEASON_HIDDEN_FIELDS = frozenset(
    {"poster", "category", "title_kk", "title_ru", "title_original", "description"}
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


def notify_keyboard(*, back: bool = True, forward: bool = False) -> InlineKeyboardMarkup:
    """«Жазылушыларға хабарлау керек пе?» — Иә/Жоқ.

    Отдельный вопрос на каждый фильм, а не глобальная настройка: каталог заливают
    пачками (десятки фильмов за вечер), и авто-рассылка на каждый превращалась в
    десятки пушей за день — за такое бота блокируют. Массовую заливку админ проводит
    с «Жоқ», а точечную новинку — с «Иә».
    """
    return _with_nav(
        [
            [
                InlineKeyboardButton(text="🔔 Иә, хабарла", callback_data=f"{NOTIFY_PREFIX}1"),
                InlineKeyboardButton(text="🔕 Жоқ", callback_data=f"{NOTIFY_PREFIX}0"),
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


def edit_keyboard(*, season_picked: bool = False) -> InlineKeyboardMarkup:
    """Меню правки: прыжок к одному полю (после ввода — сразу обратно к сводке).

    `season_picked` — выбрана серия УЖЕ СУЩЕСТВУЮЩЕГО сезона: постер/категории/
    названия/описание сериал уже несёт сам, полей для правки на этой серии нет.
    """
    fields = (
        [(f, t) for f, t in EDIT_FIELDS if f not in _SEASON_HIDDEN_FIELDS]
        if season_picked
        else list(EDIT_FIELDS)
    )
    buttons = [
        InlineKeyboardButton(text=title, callback_data=f"{EDIT_PREFIX}{field}")
        for field, title in fields
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text=_BACK_TEXT, callback_data=EDIT_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def series_root_keyboard(*, back: bool) -> InlineKeyboardMarkup:
    """Корневой экран шага «серия»: новый сериал / бар сериалдан таңдау / жеке фильм."""
    return _with_nav(
        [
            [InlineKeyboardButton(text="📺 Бар сериалдан таңдау", callback_data=SERIES_LIST)],
            [InlineKeyboardButton(text="➕ Жаңа сериал", callback_data=SERIES_NEW)],
            [InlineKeyboardButton(text="🎬 Жоқ, жеке фильм", callback_data=SERIES_NONE)],
        ],
        back=back,
    )


def series_list_keyboard(series: list[Series]) -> InlineKeyboardMarkup:
    """Список уже заведённых сериалов + «➕ Жаңа сериал» + назад к корню шага."""
    rows = [
        [InlineKeyboardButton(text=f"📺 {s.title_kk}", callback_data=f"{SERIES_PICK_PREFIX}{s.id}")]
        for s in series
    ]
    rows.append([InlineKeyboardButton(text="➕ Жаңа сериал", callback_data=SERIES_NEW)])
    rows.append([InlineKeyboardButton(text=_BACK_TEXT, callback_data=SERIES_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def season_list_keyboard(seasons: list[Season]) -> InlineKeyboardMarkup:
    """Список сезонов выбранного сериала + «➕ Жаңа маусым» + назад к списку сериалов."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"{s.season_number}-маусым", callback_data=f"{SEASON_PICK_PREFIX}{s.id}"
            )
        ]
        for s in seasons
    ]
    rows.append([InlineKeyboardButton(text="➕ Жаңа маусым", callback_data=SEASON_NEW)])
    rows.append([InlineKeyboardButton(text=_BACK_TEXT, callback_data=SERIES_LIST)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
