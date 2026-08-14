"""Бот-визард `/add` — пошаговое добавление фильма (только для админов).

Поток (FSM): видео → постер → на главную?(+баннер) → категория → title_kk → title_ru →
title_original → год → рейтинг → описание → подтверждение. По подтверждению видео уходит
копией в канал-архив (`protect_content`); постер (и горизонтальный hero-баннер, если фильм
на главной) скачиваются, нормализуются и сохраняются `MovieIngestionService`.

Навигация — данные, а не разветвлённые хендлеры: порядок шагов задан `_ORDER`, у каждого шага
свой текст (`_PROMPTS`), поэтому «⬅️ Артқа» (шаг назад), «➡️ Әрі қарай» (оставить как есть) и
точечная правка поля с экрана подтверждения работают одинаково на всех шагах. Опечатку в
названии или случайный /skip можно поправить, не начиная визард заново.

Презентация тонкая: aiogram-склейка (скачать/отправить) тут, бизнес-логика — в сервисе.
"""

from __future__ import annotations

from contextlib import suppress
from io import BytesIO
from typing import Any

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.application.services.ingestion_service import MovieIngestionService
from app.bot.keyboards.add_movie import (
    BACK,
    CANCEL,
    CATEGORY_DONE,
    CATEGORY_PREFIX,
    CONFIRM,
    EDIT,
    EDIT_BACK,
    EDIT_PREFIX,
    FEATURED_PREFIX,
    NEXT,
    category_keyboard,
    confirm_keyboard,
    edit_keyboard,
    featured_keyboard,
    step_keyboard,
)
from app.bot.security import is_admin
from app.config.settings import AppConfig
from app.domain.catalog.categories import get_category

router = Router(name="add_movie")

_SKIP = "/skip"


class AddMovie(StatesGroup):
    video = State()
    poster = State()
    featured = State()
    hero = State()
    category = State()
    title_kk = State()
    title_ru = State()
    title_original = State()
    year = State()
    rating = State()
    description = State()
    confirm = State()


# --- шаги как данные --------------------------------------------------------

# Порядок шагов. Отсюда считаются «назад»/«вперёд»: hero пропускается, если фильм не на главной.
_ORDER: tuple[State, ...] = (
    AddMovie.video,
    AddMovie.poster,
    AddMovie.featured,
    AddMovie.hero,
    AddMovie.category,
    AddMovie.title_kk,
    AddMovie.title_ru,
    AddMovie.title_original,
    AddMovie.year,
    AddMovie.rating,
    AddMovie.description,
    AddMovie.confirm,
)

_PROMPTS: dict[str | None, str] = {
    AddMovie.video.state: "🎬 1/10 — видеоны жібер (видео, не файл). /cancel — болдырмау.",
    AddMovie.poster.state: "2/10 — постерді сурет (фото) ретінде жібер.",
    AddMovie.featured.state: "3/10 — басты бетте (hero) көрсету керек пе?",
    AddMovie.hero.state: (
        "⭐ Hero-баннер: басты бетте кең көрсетіледі. Кең (горизонталь) НЕ шаршы сурет "
        "жібер — 3:2-ге қиылады, әдемі болу үшін (портрет постер емес)."
    ),
    AddMovie.category.state: (
        "4/10 — категорияларды таңда (бірнешеуін болады), содан кейін «Дайын»:"
    ),
    AddMovie.title_kk.state: "5/10 — қазақша атауы (название на казахском):",
    AddMovie.title_ru.state: "6/10 — название на русском (или /skip):",
    AddMovie.title_original.state: "7/10 — оригинальное название / English (или /skip):",
    AddMovie.year.state: "8/10 — год выпуска (напр. 1994) или /skip:",
    AddMovie.rating.state: "9/10 — рейтинг 0–10 (напр. 8.5) или /skip:",
    AddMovie.description.state: "10/10 — описание (сипаттама):",
}

_INDEX: dict[str | None, int] = {step.state: i for i, step in enumerate(_ORDER)}
_BY_STATE: dict[str | None, State] = {step.state: step for step in _ORDER}
# Имя шага («title_ru») = хвост его state («AddMovie:title_ru») = ключ значения в FSM-data.
_BY_NAME: dict[str, State] = {(step.state or "").split(":")[-1]: step for step in _ORDER}


def _name(step: State) -> str:
    return (step.state or "").split(":")[-1]


def _seek(index: int, data: dict[str, Any], direction: int) -> State | None:
    """Ближайший видимый шаг от `index` в сторону `direction` (hero — только у featured)."""
    while 0 <= index < len(_ORDER):
        step = _ORDER[index]
        if step is not AddMovie.hero or data.get("is_featured"):
            return step
        index += direction
    return None


def _next(step: State, data: dict[str, Any]) -> State | None:
    return _seek(_INDEX[step.state] + 1, data, 1)


def _previous(step: State, data: dict[str, Any]) -> State | None:
    return _seek(_INDEX[step.state] - 1, data, -1)


def _value(step: State, data: dict[str, Any]) -> str | None:
    """Что уже введено на шаге — показываем при возврате, чтобы было видно, что правим."""
    if step in (AddMovie.video, AddMovie.poster, AddMovie.hero):
        return "тіркелген ✅" if data.get(f"{_name(step)}_file_id") else None
    if step is AddMovie.featured:
        return None if "is_featured" not in data else ("Иә" if data["is_featured"] else "Жоқ")
    if step is AddMovie.category:
        return _category_titles(data) if data.get("categories") else None
    key = _name(step)
    if key not in data:
        return None
    return str(data[key]) if data[key] is not None else "— (өткізілген)"


def _has_value(step: State, data: dict[str, Any]) -> bool:
    """Есть ли что «оставить как есть» — от этого зависит кнопка «➡️ Әрі қарай»."""
    if step in (AddMovie.category, AddMovie.confirm):
        return False  # у категорий своя «Дайын», у сводки — «Сақтау»
    return _value(step, data) is not None


def _screen(step: State, data: dict[str, Any]) -> tuple[str, InlineKeyboardMarkup | None]:
    """Экран шага: текст (+ текущее значение) и клавиатура с доступной навигацией."""
    if step is AddMovie.confirm:
        return _summary(data), confirm_keyboard()
    # В режиме точечной правки «назад» всегда есть — он возвращает к сводке.
    back = bool(data.get("edit")) or _previous(step, data) is not None
    forward = _has_value(step, data)
    text = _PROMPTS[step.state]
    if (current := _value(step, data)) is not None:
        text += f"\n\nҚазір: {current}"
        if forward:
            text += "\n«➡️ Әрі қарай» — өзгеріссіз қалдыру."
    if step is AddMovie.featured:
        return text, featured_keyboard(back=back, forward=forward)
    if step is AddMovie.category:
        return text, category_keyboard(set(data.get("categories") or []), back=back)
    return text, step_keyboard(back=back, forward=forward)


# --- вспомогательное --------------------------------------------------------

def _is_admin(message: Message, config: AppConfig) -> bool:
    return message.from_user is not None and is_admin(
        message.from_user.id, config.bot.admin_user_ids
    )


async def _send(
    target: Message | CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    message = target.message if isinstance(target, CallbackQuery) else target
    if isinstance(message, Message):
        await message.answer(text, reply_markup=reply_markup)


async def _show(target: Message | CallbackQuery, state: FSMContext, step: State) -> None:
    """Перейти на шаг и показать его экран (единственный способ смены шага в визарде)."""
    await state.set_state(step)
    text, markup = _screen(step, await state.get_data())
    await _send(target, text, markup)


async def _advance(target: Message | CallbackQuery, state: FSMContext) -> None:
    """Дальше по визарду; в режиме правки одного поля — сразу обратно к сводке."""
    raw = await state.get_state()
    step = _BY_STATE.get(raw)
    if step is None:
        return
    data = await state.get_data()
    if data.get("edit"):
        # Правка «Жоқ → Иә» требует баннера: сначала добираем его, потом уже сводка.
        if step is AddMovie.featured and data.get("is_featured") and not data.get("hero_file_id"):
            await _show(target, state, AddMovie.hero)
            return
        await state.update_data(edit=False)
        await _show(target, state, AddMovie.confirm)
        return
    if (following := _next(step, data)) is not None:
        await _show(target, state, following)


async def _download(bot: Bot, file_id: str) -> bytes:
    buffer = BytesIO()
    await bot.download(file_id, destination=buffer)
    return buffer.getvalue()


# --- вход / отмена ----------------------------------------------------------

@router.message(Command("add"))
@inject
async def start_add(message: Message, state: FSMContext, config: FromDishka[AppConfig]) -> None:
    if not _is_admin(message, config):
        return
    await state.clear()
    await _show(message, state, AddMovie.video)


@router.message(Command("cancel"))
async def cancel_add(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        return
    await state.clear()
    await message.answer("❌ Болдырылмады.")


# --- навигация --------------------------------------------------------------

@router.callback_query(StateFilter(AddMovie), F.data == BACK)
async def go_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Шаг назад с сохранением всего введённого (из режима правки — обратно к сводке)."""
    step = _BY_STATE.get(await state.get_state())
    if step is None:
        await callback.answer()
        return
    data = await state.get_data()
    if data.get("edit"):
        await state.update_data(edit=False)
        await callback.answer()
        await _show(callback, state, AddMovie.confirm)
        return
    previous = _previous(step, data)
    if previous is None:
        await callback.answer("Бұл — бірінші қадам", show_alert=True)
        return
    await callback.answer()
    await _show(callback, state, previous)


@router.callback_query(StateFilter(AddMovie), F.data == NEXT)
async def go_forward(callback: CallbackQuery, state: FSMContext) -> None:
    """«Оставить как есть» — доступно только на шаге, где значение уже введено."""
    step = _BY_STATE.get(await state.get_state())
    if step is None or not _has_value(step, await state.get_data()):
        await callback.answer("Алдымен мәнін жібер", show_alert=True)
        return
    await callback.answer()
    await _advance(callback, state)


# --- шаги -------------------------------------------------------------------

@router.message(AddMovie.video, F.video)
async def step_video(message: Message, state: FSMContext) -> None:
    if message.video is None:
        return
    await state.update_data(video_file_id=message.video.file_id)
    await _advance(message, state)


@router.message(AddMovie.video)
async def step_video_retry(message: Message) -> None:
    await message.answer("Видео күтілуде. Видеоны жібер немесе /cancel.")


@router.message(AddMovie.poster, F.photo)
async def step_poster(message: Message, state: FSMContext) -> None:
    if not message.photo:
        return
    await state.update_data(poster_file_id=message.photo[-1].file_id)  # самый крупный размер
    await _advance(message, state)


@router.message(AddMovie.poster)
async def step_poster_retry(message: Message) -> None:
    await message.answer("Постер күтілуде — фото жібер немесе /cancel.")


@router.callback_query(AddMovie.featured, F.data.startswith(FEATURED_PREFIX))
async def step_featured(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        return
    featured = callback.data.removeprefix(FEATURED_PREFIX) == "1"
    await state.update_data(is_featured=featured)
    if not featured:
        await state.update_data(hero_file_id=None)
    await callback.answer()
    await _advance(callback, state)


@router.message(AddMovie.hero, F.photo)
async def step_hero(message: Message, state: FSMContext) -> None:
    if not message.photo:
        return
    await state.update_data(hero_file_id=message.photo[-1].file_id)
    await _advance(message, state)


@router.message(AddMovie.hero)
async def step_hero_retry(message: Message) -> None:
    await message.answer("Hero-сурет күтілуде — кең не шаршы фото жібер немесе /cancel.")


# DONE зарегистрирован ПЕРЕД тумблером: его callback_data тоже начинается с
# CATEGORY_PREFIX, но точное совпадение должно перехватываться раньше overlap-матча.
@router.callback_query(AddMovie.category, F.data == CATEGORY_DONE)
async def step_category_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("categories"):
        await callback.answer("Кемінде бір категорияны таңда", show_alert=True)
        return
    await callback.answer()
    await _advance(callback, state)


@router.callback_query(AddMovie.category, F.data.startswith(CATEGORY_PREFIX))
async def step_category_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        return
    slug = callback.data.removeprefix(CATEGORY_PREFIX)
    if get_category(slug) is None:
        await callback.answer("Белгісіз категория", show_alert=True)
        return
    data = await state.get_data()
    selected = set(data.get("categories") or [])
    if slug in selected:
        selected.discard(slug)
    else:
        selected.add(slug)
    await state.update_data(categories=sorted(selected))
    await callback.answer("✅ қосылды" if slug in selected else "➖ алынды")
    # Перерисовываем ту же клавиатуру с обновлёнными галочками (не плодим сообщения).
    if isinstance(callback.message, Message):
        with suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(
                reply_markup=category_keyboard(selected, back=True)
            )


@router.message(AddMovie.title_kk, F.text)
async def step_title_kk(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        return
    await state.update_data(title_kk=title)
    await _advance(message, state)


@router.message(AddMovie.title_ru, F.text)
async def step_title_ru(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    await state.update_data(title_ru=None if value == _SKIP else value)
    await _advance(message, state)


@router.message(AddMovie.title_original, F.text)
async def step_title_original(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    await state.update_data(title_original=None if value == _SKIP else value)
    await _advance(message, state)


@router.message(AddMovie.year, F.text)
async def step_year(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if value == _SKIP:
        await state.update_data(year=None)
    elif value.isdigit():
        await state.update_data(year=int(value))
    else:
        await message.answer("Год — целое число (1994) или /skip.")
        return
    await _advance(message, state)


@router.message(AddMovie.rating, F.text)
async def step_rating(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if value == _SKIP:
        await state.update_data(rating=None)
    else:
        try:
            await state.update_data(rating=float(value.replace(",", ".")))
        except ValueError:
            await message.answer("Рейтинг — число (8.5) или /skip.")
            return
    await _advance(message, state)


@router.message(AddMovie.description, F.text)
async def step_description(message: Message, state: FSMContext) -> None:
    description = (message.text or "").strip()
    if not description:
        return
    await state.update_data(description=description)
    await _advance(message, state)


# --- подтверждение и правка -------------------------------------------------

# EDIT_BACK зарегистрирован ПЕРЕД выбором поля: его callback_data тоже начинается с
# EDIT_PREFIX (как «Дайын» у категорий) — точное совпадение должно ловиться раньше.
@router.callback_query(AddMovie.confirm, F.data == EDIT_BACK)
async def edit_menu_close(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        with suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(reply_markup=confirm_keyboard())


@router.callback_query(AddMovie.confirm, F.data == EDIT)
async def edit_menu_open(callback: CallbackQuery, state: FSMContext) -> None:
    """Меню правки прямо на сводке — чтобы не идти «назад» через все шаги ради одного поля."""
    data = await state.get_data()
    await callback.answer()
    if isinstance(callback.message, Message):
        with suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(
                reply_markup=edit_keyboard(is_featured=bool(data.get("is_featured")))
            )


@router.callback_query(AddMovie.confirm, F.data.startswith(EDIT_PREFIX))
async def edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    """Прыжок к одному шагу; после ввода `_advance` вернёт обратно к сводке."""
    if callback.data is None:
        return
    step = _BY_NAME.get(callback.data.removeprefix(EDIT_PREFIX))
    if step is None or step is AddMovie.confirm:
        await callback.answer("Белгісіз өріс", show_alert=True)
        return
    await state.update_data(edit=True)
    await callback.answer()
    await _show(callback, state, step)


@router.callback_query(AddMovie.confirm, F.data == CONFIRM)
@inject
async def confirm_add(
    callback: CallbackQuery,
    state: FSMContext,
    bot: FromDishka[Bot],
    config: FromDishka[AppConfig],
    ingestion: FromDishka[MovieIngestionService],
) -> None:
    data = await state.get_data()
    await callback.answer()
    await _send(callback, "⏳ Сақталуда…")
    try:
        # 1) копия видео в канал-архив (protect_content) → стабильный file_id для выдачи
        archive_file_id = await _archive_video(bot, config, str(data["video_file_id"]))
        # 2) постер (и hero-баннер, если фильм на главной) скачиваем → байты для сервиса
        poster_bytes = await _download(bot, str(data["poster_file_id"]))
        hero_file_id = data.get("hero_file_id")
        hero_bytes = await _download(bot, str(hero_file_id)) if hero_file_id else None

        movie = await ingestion.ingest(
            title_kk=str(data["title_kk"]),
            title_ru=data.get("title_ru"),
            title_original=data.get("title_original"),
            categories=list(data["categories"]),
            description=str(data["description"]),
            year=data.get("year"),
            rating=data.get("rating"),
            is_featured=bool(data.get("is_featured")),
            video_file_id=archive_file_id,
            poster_bytes=poster_bytes,
            hero_bytes=hero_bytes,
        )
    except Exception:
        # Визард не должен зависать на «⏳ Сақталуда…»: любую ошибку (битая картинка, сеть,
        # БД) показываем внятно, но ВВЕДЁННОЕ СОХРАНЯЕМ — админ жмёт «Сақтау» ещё раз или
        # правит поле, а не заполняет визард заново.
        await _send(callback, "⚠️ Сақтау кезінде қате (сурет/желі). Қайта көріңіз:")
        await _show(callback, state, AddMovie.confirm)
        return
    await state.clear()
    await _send(callback, f"✅ «{movie.title_kk}» қосылды. ID: {movie.id}")


@router.callback_query(AddMovie.confirm, F.data == CANCEL)
async def confirm_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Болдырылмады")
    await _send(callback, "❌ Болдырылмады.")


# --- helpers ----------------------------------------------------------------

async def _archive_video(bot: Bot, config: AppConfig, video_file_id: str) -> str:
    """Положить копию видео в канал-архив (protect_content), вернуть его file_id.

    Если канал не настроен (`archive_channel_id == 0`) — отдаём исходный file_id из лички.
    """
    if not config.bot.archive_channel_id:
        return video_file_id
    sent = await bot.send_video(
        config.bot.archive_channel_id, video_file_id, protect_content=True
    )
    return sent.video.file_id if sent.video is not None else video_file_id


def _category_titles(data: dict[str, Any]) -> str:
    slugs = list(data.get("categories") or [])
    titles = [(cat.title_ru if (cat := get_category(s)) is not None else s) for s in slugs]
    return ", ".join(titles) if titles else "—"


def _summary(data: dict[str, Any]) -> str:
    # Для featured показываем, что баннер уже пришёл (у is_featured всегда есть hero_file_id).
    featured = "Иә (баннер тіркелді)" if data.get("is_featured") else "Жоқ"
    return "\n".join(
        [
            "Тексер және сақта (проверь и сохрани):",
            f"🎬 KK: {data.get('title_kk') or '—'}",
            f"🇷🇺 RU: {data.get('title_ru') or '—'}",
            f"🌐 Ориг.: {data.get('title_original') or '—'}",
            f"🗂 Категория: {_category_titles(data)}",
            f"📌 Басты бетте (hero): {featured}",
            f"📅 Год: {data.get('year') or '—'}",
            f"⭐ Рейтинг: {data.get('rating') or '—'}",
            f"📝 {data.get('description') or '—'}",
            "",
            "«✏️ Түзету» — жеке өрісті түзету.",
        ]
    )
