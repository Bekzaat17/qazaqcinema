"""Бот-визард `/add` — пошаговое добавление фильма (только для админов).

Поток (FSM): видео → категория → сериал? → постер → title_kk → title_ru →
title_original → год → рейтинг → описание → рассылка? → подтверждение. По
подтверждению видео уходит копией в канал-архив (`protect_content`); постер
скачивается, нормализуется и сохраняется `MovieIngestionService`.

Картинка у фильма ровно ОДНА — постер (решение 2026-08-19). Ни «показывать на главной?»,
ни отдельного широкого баннера визард больше не спрашивает: hero — это фильм дня, туда по
очереди попадает весь каталог, а широкую поверхность фронт делает из того же постера
(увеличенная размытая копия фоном). Просить у админа вторую картинку к каждому из сотен
фильмов — работа, которая ничего не добавляет.

Навигация — данные, а не разветвлённые хендлеры: порядок шагов задан `_ORDER`, у каждого шага
свой текст (`_PROMPTS`), поэтому «⬅️ Артқа» (шаг назад), «➡️ Әрі қарай» (оставить как есть) и
точечная правка поля с экрана подтверждения работают одинаково на всех шагах. Опечатку в
названии или случайный /skip можно поправить, не начиная визард заново.

Сериалы (решение 2026-08-28): шаг «сериал» — единственное настоящее ветвление визарда,
и оно намеренно НЕ разветвляет сами хендлеры/шаги (принцип «условных шагов нет», см.
CLAUDE.md 2026-08-19) — это внутренний под-диалог ОДНОГО шага (кнопки → кнопки → текст),
как уже устроен мультивыбор категорий. А вот `_next`/`_previous` при серии УЖЕ
СУЩЕСТВУЮЩЕГО сезона осознанно перескакивают постер/категорию/названия/описание —
это не тот же антипаттерн: для такой серии эти поля просто не существуют (их несёт
сезон, см. `domain/entities/season.Season`), а не «временно не нужны».

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
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.application.services.ingestion_service import MovieIngestionService
from app.application.services.series_service import SeriesService
from app.bot.keyboards.add_movie import (
    BACK,
    CANCEL,
    CATEGORY_DONE,
    CATEGORY_PREFIX,
    CONFIRM,
    EDIT,
    EDIT_BACK,
    EDIT_PREFIX,
    NEXT,
    NOTIFY_PREFIX,
    SEASON_NEW,
    SEASON_PICK_PREFIX,
    SERIES_LIST,
    SERIES_MENU,
    SERIES_NEW,
    SERIES_NONE,
    SERIES_PICK_PREFIX,
    category_keyboard,
    confirm_keyboard,
    edit_keyboard,
    notify_keyboard,
    season_list_keyboard,
    series_list_keyboard,
    series_root_keyboard,
    step_keyboard,
)
from app.bot.security import is_admin
from app.config.settings import AppConfig
from app.domain.catalog.categories import get_category

router = Router(name="add_movie")

_SKIP = "/skip"


class AddMovie(StatesGroup):
    video = State()
    category = State()
    series = State()
    poster = State()
    title_kk = State()
    title_ru = State()
    title_original = State()
    year = State()
    rating = State()
    description = State()
    notify = State()
    confirm = State()


# --- шаги как данные --------------------------------------------------------

# Порядок шагов. Отсюда считаются «назад»/«вперёд» — условных шагов в самом списке нет
# (см. модуль-докстринг про _SEASON_SKIP — это НЕ то же самое, что убранная в 2026-08-19
# условность: тут поля физически не существуют у серии готового сезона).
_ORDER: tuple[State, ...] = (
    AddMovie.video,
    AddMovie.category,
    AddMovie.series,
    AddMovie.poster,
    AddMovie.title_kk,
    AddMovie.title_ru,
    AddMovie.title_original,
    AddMovie.year,
    AddMovie.rating,
    AddMovie.description,
    AddMovie.notify,
    AddMovie.confirm,
)

# Шаги, которые пропускаются, когда выбрана серия УЖЕ СУЩЕСТВУЮЩЕГО сезона (season_id
# в FSM-данных): постер/категории/названия/описание сезон уже несёт сам.
_SEASON_SKIP: frozenset[State] = frozenset(
    {
        AddMovie.poster,
        AddMovie.category,
        AddMovie.title_kk,
        AddMovie.title_ru,
        AddMovie.title_original,
        AddMovie.description,
    }
)

_PROMPTS: dict[str | None, str] = {
    AddMovie.video.state: "🎬 1/11 — видеоны жібер (видео, не файл). /cancel — болдырмау.",
    AddMovie.category.state: (
        "2/11 — категорияларды таңда (бірнешеуін болады), содан кейін «Дайын»:"
    ),
    AddMovie.series.state: "3/11 — бұл сериалдың бөлігі ме?",
    AddMovie.poster.state: "4/11 — постерді сурет (фото) ретінде жібер.",
    AddMovie.title_kk.state: "5/11 — қазақша атауы (название на казахском):",
    AddMovie.title_ru.state: "6/11 — название на русском (или /skip):",
    AddMovie.title_original.state: "7/11 — оригинальное название / English (или /skip):",
    AddMovie.year.state: "8/11 — год выпуска (напр. 1994) или /skip:",
    AddMovie.rating.state: "9/11 — рейтинг 0–10 (напр. 8.5) или /skip:",
    AddMovie.description.state: "10/11 — описание (сипаттама):",
    AddMovie.notify.state: (
        "11/11 — жазылушыларға жаңа фильм туралы хабарлама жіберу керек пе?\n\n"
        "Хабарлама тек хабарландыруды ҚОСҚАНДАРҒА барады. Каталогты топтап толтырып "
        "жатсаң — «🔕 Жоқ» (әйтпесе бір күнде ондаған хабарлама кетеді)."
    ),
}

_INDEX: dict[str | None, int] = {step.state: i for i, step in enumerate(_ORDER)}
_BY_STATE: dict[str | None, State] = {step.state: step for step in _ORDER}
# Имя шага («title_ru») = хвост его state («AddMovie:title_ru») = ключ значения в FSM-data.
_BY_NAME: dict[str, State] = {(step.state or "").split(":")[-1]: step for step in _ORDER}


def _name(step: State) -> str:
    return (step.state or "").split(":")[-1]


def _season_active(data: dict[str, Any]) -> bool:
    """Серия УЖЕ СУЩЕСТВУЮЩЕГО сезона выбрана — постер/названия/категории/описание
    у неё не спрашиваются (несёт сезон)."""
    return data.get("season_id") is not None


def _step_at(index: int) -> State | None:
    """Шаг по индексу или None за краями списка (первый «назад», последний «вперёд»)."""
    return _ORDER[index] if 0 <= index < len(_ORDER) else None


def _next(step: State, data: dict[str, Any]) -> State | None:
    index = _INDEX[step.state] + 1
    while (candidate := _step_at(index)) is not None:
        if candidate in _SEASON_SKIP and _season_active(data):
            index += 1
            continue
        return candidate
    return None


def _previous(step: State, data: dict[str, Any]) -> State | None:
    index = _INDEX[step.state] - 1
    while (candidate := _step_at(index)) is not None:
        if candidate in _SEASON_SKIP and _season_active(data):
            index -= 1
            continue
        return candidate
    return None


def _series_summary(data: dict[str, Any]) -> str | None:
    """Что выбрано на шаге «сериал» — для «Қазір: …» и сводки. None — ещё не решали."""
    if not data.get("series_decided"):
        return None
    if data.get("season_id") is not None:
        title = data.get("series_title_display") or "?"
        number = data.get("season_number_display", "?")
        return f"«{title}» — {number}-маусым"
    if data.get("season_new_number") is not None:
        title = data.get("series_new_title") or data.get("series_title_display") or "?"
        return f"«{title}» — {data['season_new_number']}-маусым (жаңа)"
    return "Жеке фильм"


def _value(step: State, data: dict[str, Any]) -> str | None:
    """Что уже введено на шаге — показываем при возврате, чтобы было видно, что правим."""
    if step is AddMovie.video:
        return "тіркелген ✅" if data.get("video_file_id") else None
    if step is AddMovie.poster:
        if data.get("season_id") is not None:
            return "тіркелген ✅ (маусым постері)"
        return "тіркелген ✅" if data.get("poster_file_id") else None
    if step is AddMovie.series:
        return _series_summary(data)
    if step is AddMovie.notify:
        return None if "notify" not in data else ("Иә" if data["notify"] else "Жоқ")
    if step is AddMovie.category:
        return _category_titles(data) if data.get("categories") else None
    key = _name(step)
    if key not in data:
        return None
    return str(data[key]) if data[key] is not None else "— (өткізілген)"


def _has_value(step: State, data: dict[str, Any]) -> bool:
    """Есть ли что «оставить как есть» — от этого зависит кнопка «➡️ Әрі қарай»."""
    if step in (AddMovie.category, AddMovie.series, AddMovie.confirm):
        return False  # у категорий своя «Дайын», у сериала — свои кнопки, у сводки — «Сақтау»
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
    if step is AddMovie.notify:
        return text, notify_keyboard(back=back, forward=forward)
    if step is AddMovie.category:
        return text, category_keyboard(set(data.get("categories") or []), back=back)
    if step is AddMovie.series:
        return text, series_root_keyboard(back=back)
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


async def _edit(
    callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    """Перерисовать текущее сообщение (под-экраны шага «сериал») — не плодим сообщения."""
    if isinstance(callback.message, Message):
        with suppress(TelegramBadRequest):
            await callback.message.edit_text(text, reply_markup=reply_markup)


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


@router.callback_query(AddMovie.notify, F.data.startswith(NOTIFY_PREFIX))
async def step_notify(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        return
    await state.update_data(notify=callback.data.removeprefix(NOTIFY_PREFIX) == "1")
    await callback.answer()
    await _advance(callback, state)


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


# --- шаг «сериал» -------------------------------------------------------------

@router.callback_query(AddMovie.series, F.data == SERIES_NONE)
async def series_pick_none(callback: CallbackQuery, state: FSMContext) -> None:
    """«Жоқ, жеке фильм» — обычный самостоятельный фильм, как раньше."""
    await callback.answer()
    await state.update_data(
        series_decided=True,
        series_id=None,
        series_new_title=None,
        series_title_display=None,
        season_id=None,
        season_new_number=None,
        season_number_display=None,
        series_await=None,
    )
    await _advance(callback, state)


@router.callback_query(AddMovie.series, F.data == SERIES_NEW)
async def series_pick_new(callback: CallbackQuery, state: FSMContext) -> None:
    """«➕ Жаңа сериал» — сначала имя сериала, потом номер сезона (текстом)."""
    await callback.answer()
    await state.update_data(
        series_await="name", series_id=None, series_title_display=None, season_id=None
    )
    await _edit(callback, "Жаңа сериалдың атауы (қазақша):")


@router.callback_query(AddMovie.series, F.data == SERIES_LIST)
@inject
async def series_pick_list(
    callback: CallbackQuery, state: FSMContext, series: FromDishka[SeriesService]
) -> None:
    """«📺 Бар сериалдан таңдау» — список уже заведённых сериалов."""
    await callback.answer()
    items = await series.list_series()
    if items:
        await _edit(callback, "Сериалды таңда:", series_list_keyboard(items))
    else:
        await _edit(
            callback,
            "Әзірге сериал жоқ. Жаңасын аш:",
            InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Жаңа сериал", callback_data=SERIES_NEW)]
                ]
            ),
        )


@router.callback_query(AddMovie.series, F.data == SERIES_MENU)
async def series_menu_root(callback: CallbackQuery, state: FSMContext) -> None:
    """Назад из списка сериалов к корневым 3 кнопкам шага."""
    await callback.answer()
    data = await state.get_data()
    back = bool(data.get("edit")) or _previous(AddMovie.series, data) is not None
    text = _PROMPTS[AddMovie.series.state]
    if (summary := _series_summary(data)) is not None:
        text += f"\n\nҚазір: {summary}"
    await _edit(callback, text, series_root_keyboard(back=back))


@router.callback_query(AddMovie.series, F.data.startswith(SERIES_PICK_PREFIX))
@inject
async def series_pick_existing(
    callback: CallbackQuery, state: FSMContext, series: FromDishka[SeriesService]
) -> None:
    """Выбран конкретный сериал — показываем его сезоны."""
    if callback.data is None:
        return
    series_id = int(callback.data.removeprefix(SERIES_PICK_PREFIX))
    picked = await series.get_series(series_id)
    if picked is None:
        await callback.answer("Табылмады", show_alert=True)
        return
    seasons = await series.list_seasons(series_id)
    await state.update_data(
        series_id=series_id, series_title_display=picked.title_kk, series_new_title=None
    )
    await callback.answer()
    await _edit(callback, f"«{picked.title_kk}» — маусымды таңда:", season_list_keyboard(seasons))


@router.callback_query(AddMovie.series, F.data == SEASON_NEW)
async def season_pick_new(callback: CallbackQuery, state: FSMContext) -> None:
    """«➕ Жаңа маусым» — под текущим сериалом (уже выбранным или только что созданным)."""
    await callback.answer()
    await state.update_data(
        series_await="season_number", season_id=None, season_number_display=None
    )
    await _edit(callback, "Нешінші маусым? (сан жібер, мысалы 1)")


@router.callback_query(AddMovie.series, F.data.startswith(SEASON_PICK_PREFIX))
@inject
async def season_pick_existing(
    callback: CallbackQuery, state: FSMContext, series: FromDishka[SeriesService]
) -> None:
    """Выбран УЖЕ СУЩЕСТВУЮЩИЙ сезон — постер/название/категории/описание уже его."""
    if callback.data is None:
        return
    season_id = int(callback.data.removeprefix(SEASON_PICK_PREFIX))
    season = await series.get_season(season_id)
    if season is None:
        await callback.answer("Табылмады", show_alert=True)
        return
    await state.update_data(
        season_id=season_id,
        season_number_display=season.season_number,
        season_new_number=None,
        series_decided=True,
        series_await=None,
    )
    await callback.answer()
    await _advance(callback, state)


@router.message(AddMovie.series, F.text)
async def series_text_input(message: Message, state: FSMContext) -> None:
    """Текст, ожидаемый под-диалогом шага «сериал»: имя нового сериала / номер сезона."""
    value = (message.text or "").strip()
    data = await state.get_data()
    awaiting = data.get("series_await")
    if awaiting == "name":
        if not value:
            return
        await state.update_data(series_new_title=value, series_await="season_number")
        await message.answer("Нешінші маусым? (сан жібер, мысалы 1)")
        return
    if awaiting == "season_number":
        if not value.isdigit():
            await message.answer("Маусым нөмірі — сан (мысалы 1). Қайта жібер:")
            return
        await state.update_data(
            season_new_number=int(value), series_await=None, series_decided=True
        )
        await _advance(message, state)
        return
    await message.answer("Жоғарыдағы хабарламадағы түймелердің бірін бас.")


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
    await callback.answer()
    data = await state.get_data()
    if isinstance(callback.message, Message):
        with suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(
                reply_markup=edit_keyboard(season_picked=_season_active(data))
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
    series: FromDishka[SeriesService],
) -> None:
    data = await state.get_data()
    await callback.answer()
    await _send(callback, "⏳ Сақталуда…")
    try:
        # 1) копия видео в канал-архив (protect_content) → стабильный file_id для выдачи
        archive_file_id = await _archive_video(bot, config, str(data["video_file_id"]))

        # 2) сериал/сезон: три случая — существующий сезон / новый сезон (+новый сериал
        #    при необходимости) / обычный самостоятельный фильм.
        season_id = data.get("season_id")
        season_new_number = data.get("season_new_number")
        if season_id is None and season_new_number is not None:
            # Новый сезон — постер грузим один раз, он же станет постером сезона.
            fresh_poster = await _download(bot, str(data["poster_file_id"]))
            series_id = data.get("series_id")
            if series_id is None:
                created_series = await series.create_series(str(data["series_new_title"]))
                if created_series.id is None:
                    raise ValueError("Сериал сақталды, бірақ id жоқ")
                series_id = created_series.id
            created_season = await series.create_season(
                series_id,
                int(season_new_number),
                fresh_poster,
                title_kk=str(data["title_kk"]),
                description=str(data["description"]),
                categories=list(data["categories"]),
            )
            season_id = created_season.id

        movie = await ingestion.ingest(
            title_kk=None if season_id is not None else str(data["title_kk"]),
            title_ru=data.get("title_ru"),
            title_original=data.get("title_original"),
            categories=None if season_id is not None else list(data["categories"]),
            description=None if season_id is not None else str(data["description"]),
            year=data.get("year"),
            rating=data.get("rating"),
            notify=bool(data.get("notify")),
            video_file_id=archive_file_id,
            poster_bytes=(
                None if season_id is not None else await _download(bot, str(data["poster_file_id"]))
            ),
            season_id=season_id,
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
    """Сводка перед сохранением.

    У серии УЖЕ СУЩЕСТВУЮЩЕГО сезона (`_season_active`) название/категории/описание не
    спрашивались (несёт сезон) — их и не показываем. А вот при создании НОВОГО сезона
    (`season_new_number` без `season_id`) эти поля реально собраны визардом (они станут
    данными сезона) — показываем как у обычного фильма.
    """
    lines = ["Тексер және сақта (проверь и сохрани):"]
    if not _season_active(data):
        lines += [
            f"🎬 KK: {data.get('title_kk') or '—'}",
            f"🇷🇺 RU: {data.get('title_ru') or '—'}",
            f"🌐 Ориг.: {data.get('title_original') or '—'}",
            f"🗂 Категория: {_category_titles(data)}",
        ]
    lines.append(f"📺 Сериал: {_series_summary(data) or 'Жеке фильм'}")
    lines += [
        f"📅 Год: {data.get('year') or '—'}",
        f"⭐ Рейтинг: {data.get('rating') or '—'}",
    ]
    if not _season_active(data):
        lines.append(f"📝 {data.get('description') or '—'}")
    lines += [
        f"🔔 Хабарлама: {'Иә' if data.get('notify') else 'Жоқ'}",
        "",
        "«✏️ Түзету» — жеке өрісті түзету.",
    ]
    return "\n".join(lines)
