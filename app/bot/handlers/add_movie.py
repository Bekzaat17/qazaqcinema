"""Бот-визард `/add` — пошаговое добавление фильма (только для админов).

Поток (FSM): видео → постер → на главную?(+баннер) → категория → title_kk → title_ru →
title_original → год → рейтинг → описание → подтверждение. По подтверждению видео уходит
копией в канал-архив (`protect_content`); постер (и горизонтальный hero-баннер, если фильм
на главной) скачиваются, нормализуются и сохраняются `MovieIngestionService`.

Презентация тонкая: aiogram-склейка (скачать/отправить) тут, бизнес-логика — в сервисе.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.application.services.ingestion_service import MovieIngestionService
from app.bot.keyboards.add_movie import (
    CANCEL,
    CATEGORY_PREFIX,
    CONFIRM,
    FEATURED_PREFIX,
    category_keyboard,
    confirm_keyboard,
    featured_keyboard,
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


def _is_admin(message: Message, config: AppConfig) -> bool:
    return message.from_user is not None and is_admin(
        message.from_user.id, config.bot.admin_user_ids
    )


async def _reply(
    callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    if isinstance(callback.message, Message):
        await callback.message.answer(text, reply_markup=reply_markup)


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
    await state.set_state(AddMovie.video)
    await message.answer(
        "🎬 Жаңа фильм. 1/10 — видеоны жібер (видео, не файл). /cancel — болдырмау."
    )


@router.message(Command("cancel"))
async def cancel_add(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        return
    await state.clear()
    await message.answer("❌ Болдырылмады.")


# --- шаги -------------------------------------------------------------------

@router.message(AddMovie.video, F.video)
async def step_video(message: Message, state: FSMContext) -> None:
    if message.video is None:
        return
    await state.update_data(video_file_id=message.video.file_id)
    await state.set_state(AddMovie.poster)
    await message.answer("2/10 — постерді сурет (фото) ретінде жібер.")


@router.message(AddMovie.video)
async def step_video_retry(message: Message) -> None:
    await message.answer("Видео күтілуде. Видеоны жібер немесе /cancel.")


@router.message(AddMovie.poster, F.photo)
async def step_poster(message: Message, state: FSMContext) -> None:
    if not message.photo:
        return
    await state.update_data(poster_file_id=message.photo[-1].file_id)  # самый крупный размер
    await state.set_state(AddMovie.featured)
    await message.answer(
        "3/10 — басты бетте (hero) көрсету керек пе?", reply_markup=featured_keyboard()
    )


@router.message(AddMovie.poster)
async def step_poster_retry(message: Message) -> None:
    await message.answer("Постер күтілуде — фото жібер немесе /cancel.")


@router.callback_query(AddMovie.featured, F.data.startswith(FEATURED_PREFIX))
async def step_featured(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        return
    featured = callback.data.removeprefix(FEATURED_PREFIX) == "1"
    await state.update_data(is_featured=featured)
    await callback.answer()
    if featured:
        await state.set_state(AddMovie.hero)
        await _reply(callback, "Басты бетке горизонталь баннер (фото) жібер:")
    else:
        await state.update_data(hero_file_id=None)
        await state.set_state(AddMovie.category)
        await _reply(callback, "4/10 — категорияны таңда:", category_keyboard())


@router.message(AddMovie.hero, F.photo)
async def step_hero(message: Message, state: FSMContext) -> None:
    if not message.photo:
        return
    await state.update_data(hero_file_id=message.photo[-1].file_id)
    await state.set_state(AddMovie.category)
    await message.answer("4/10 — категорияны таңда:", reply_markup=category_keyboard())


@router.message(AddMovie.hero)
async def step_hero_retry(message: Message) -> None:
    await message.answer("Баннер күтілуде — горизонталь фото жібер немесе /cancel.")


@router.callback_query(AddMovie.category, F.data.startswith(CATEGORY_PREFIX))
async def step_category(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        return
    slug = callback.data.removeprefix(CATEGORY_PREFIX)
    if get_category(slug) is None:
        await callback.answer("Белгісіз категория", show_alert=True)
        return
    await state.update_data(category=slug)
    await state.set_state(AddMovie.title_kk)
    await callback.answer()
    await _reply(callback, "5/10 — қазақша атауы (название на казахском):")


@router.message(AddMovie.title_kk, F.text)
async def step_title_kk(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        return
    await state.update_data(title_kk=title)
    await state.set_state(AddMovie.title_ru)
    await message.answer("6/10 — название на русском (или /skip):")


@router.message(AddMovie.title_ru, F.text)
async def step_title_ru(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    await state.update_data(title_ru=None if value == _SKIP else value)
    await state.set_state(AddMovie.title_original)
    await message.answer("7/10 — оригинальное название / English (или /skip):")


@router.message(AddMovie.title_original, F.text)
async def step_title_original(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    await state.update_data(title_original=None if value == _SKIP else value)
    await state.set_state(AddMovie.year)
    await message.answer("8/10 — год выпуска (напр. 1994) или /skip:")


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
    await state.set_state(AddMovie.rating)
    await message.answer("9/10 — рейтинг 0–10 (напр. 8.5) или /skip:")


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
    await state.set_state(AddMovie.description)
    await message.answer("10/10 — описание (сипаттама):")


@router.message(AddMovie.description, F.text)
async def step_description(message: Message, state: FSMContext) -> None:
    description = (message.text or "").strip()
    if not description:
        return
    await state.update_data(description=description)
    data = await state.get_data()
    await state.set_state(AddMovie.confirm)
    await message.answer(_summary(data), reply_markup=confirm_keyboard())


# --- подтверждение ----------------------------------------------------------

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
    await _reply(callback, "⏳ Сақталуда…")
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
            category=str(data["category"]),
            description=str(data["description"]),
            year=data.get("year"),
            rating=data.get("rating"),
            is_featured=bool(data.get("is_featured")),
            video_file_id=archive_file_id,
            poster_bytes=poster_bytes,
            hero_bytes=hero_bytes,
        )
    except Exception:
        # Визард не должен зависать на «⏳ Сақталуда…»: любую ошибку (битая картинка,
        # сеть, БД) показываем внятно и сбрасываем FSM, чтобы можно было начать заново.
        await state.clear()
        await _reply(callback, "⚠️ Сақтау кезінде қате (сурет/желі). /add арқылы қайта бастаңыз.")
        return
    await state.clear()
    await _reply(callback, f"✅ «{movie.title_kk}» қосылды. ID: {movie.id}")


@router.callback_query(AddMovie.confirm, F.data == CANCEL)
async def confirm_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Болдырылмады")
    await _reply(callback, "❌ Болдырылмады.")


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


def _summary(data: dict[str, Any]) -> str:
    category = get_category(str(data["category"]))
    category_title = category.title_ru if category is not None else data["category"]
    featured = "Иә" if data.get("is_featured") else "Жоқ"
    return "\n".join(
        [
            "Тексер және сақта (проверь и сохрани):",
            f"🎬 KK: {data['title_kk']}",
            f"🇷🇺 RU: {data.get('title_ru') or '—'}",
            f"🌐 Ориг.: {data.get('title_original') or '—'}",
            f"🗂 Категория: {category_title}",
            f"📌 Басты бетте (hero): {featured}",
            f"📅 Год: {data.get('year') or '—'}",
            f"⭐ Рейтинг: {data.get('rating') or '—'}",
            f"📝 {data['description']}",
        ]
    )
