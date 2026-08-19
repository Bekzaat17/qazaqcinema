"""Команда `/daily` — посмотреть и закрепить сегодняшний бесплатный фильм (только админ).

Обычно фильм дня выбирает ротация, и вмешиваться не нужно. Команда — на особый день:
вышла новинка, праздник, реклама у блогера. Закреп держится до местной полуночи и
пропадает сам, поэтому «забыть снять» его невозможно.

Презентация тонкая: разбор аргумента и текст ответа тут, вся логика — в сервисе.
"""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.application.services.daily_service import DailyMovieService
from app.bot.security import is_admin
from app.config.settings import AppConfig

router = Router(name="daily")


@router.message(Command("daily"))
@inject
async def daily_command(
    message: Message,
    command: CommandObject,
    config: FromDishka[AppConfig],
    daily: FromDishka[DailyMovieService],
) -> None:
    if message.from_user is None or not is_admin(message.from_user.id, config.bot.admin_user_ids):
        return
    now = datetime.now(UTC)
    argument = (command.args or "").strip()

    if not argument:
        movie = await daily.today(now)
        if movie is None:
            await message.answer("Каталог бос — бүгінгі фильм жоқ.")
            return
        await message.answer(
            f"🎁 Бүгінгі тегін фильм: «{movie.title_kk}» (ID: {movie.id})\n\n"
            "Ауыстыру: /daily <ID>. Түн ортасында ротация өз бетінше жалғасады."
        )
        return

    if not argument.isdigit():
        await message.answer("ID сан болуы керек. Мысалы: /daily 132")
        return

    movie = await daily.pin_today(int(argument), now)
    if movie is None:
        await message.answer(f"ID {argument} фильмі табылмады.")
        return
    await message.answer(
        f"✅ Бүгінгі тегін фильм: «{movie.title_kk}» (ID: {movie.id}).\n"
        "Басты бет жаңарды. Түн ортасынан кейін — қайтадан ротация."
    )
