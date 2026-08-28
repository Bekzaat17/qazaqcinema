"""Команда `/milestone` — веха роста на временной шкале (только админ).

Без аргумента — последние вехи (свериться, что уже отмечено). С текстом — новая
запись «прямо сейчас» (без возможности задать дату задним числом, сознательно: веха
пишется В МОМЕНТ, когда фичу вкатили, а не восстанавливается по памяти). Список потом
смотрят рядом с историей `daily_reports` — сравнение «до/после» человек делает сам.

Презентация тонкая: разбор аргумента и текст ответа тут, вся логика — в сервисе.
"""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.application.services.milestone_service import MilestoneService
from app.bot.security import is_admin
from app.config.settings import AppConfig

router = Router(name="milestone")

_LIST_LIMIT = 10


@router.message(Command("milestone"))
@inject
async def milestone_command(
    message: Message,
    command: CommandObject,
    config: FromDishka[AppConfig],
    milestones: FromDishka[MilestoneService],
) -> None:
    if message.from_user is None or not is_admin(message.from_user.id, config.bot.admin_user_ids):
        return
    label = (command.args or "").strip()

    if not label:
        recent = await milestones.list_recent(_LIST_LIMIT)
        if not recent:
            await message.answer(
                "Вехалар әлі жоқ.\nЖаңа веха: /milestone Күн фильмі іске қосылды"
            )
            return
        lines = "\n".join(f"• {m.occurred_at:%d.%m.%Y} — {m.label}" for m in recent)
        await message.answer(f"📍 <b>Соңғы вехалар</b>\n{lines}")
        return

    milestone = await milestones.add(label, datetime.now(UTC), message.from_user.id)
    await message.answer(f"✅ Веха жазылды: «{milestone.label}» ({milestone.occurred_at:%d.%m.%Y})")
