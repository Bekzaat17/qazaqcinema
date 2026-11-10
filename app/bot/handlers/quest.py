from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.bot.keyboards.common import quest_keyboard
from app.config.settings import AppConfig

router = Router(name="quest")
QUEST_GREETING = (
    "🏡 QazaqQuest — өз ауылыңды құр!\n\n"
    "Сиқырлы орманды зертте, қазақша тапсырмаларды орында, рухтарды оят. "
    "Материал жинап, киіз үй, құдық және шеберхана сал.\n\n"
    "🏆 Күн сайын үш сынақ, 300 ұпайға дейін. Апталық рейтингте бақ сына!"
)


@router.message(Command("quest"), F.chat.type == "private")
@inject
async def handle_quest(message: Message, config: FromDishka[AppConfig]) -> None:
    await message.answer(QUEST_GREETING, reply_markup=quest_keyboard(config.bot.webapp_url))
