"""Движение в публичном канале: кто подписался, кто ушёл (апдейты `chat_member`).

Telegram присылает их боту-администратору на каждый вход и выход в канале. Считаем по
головам, потому что `getChatMemberCount` отдаёт только итог, а он скрывает ровно то, ради
чего цифра в отчёте и нужна: «пришли 40, ушли 35» и «не было движения» — один и тот же
«+5». Отток из итога не виден никак.

Тонкая презентация: разобрать апдейт → запись в журнал. Что считать входом и что выходом,
решают фильтры aiogram (`JOIN_TRANSITION` / `LEAVE_TRANSITION`) — они же разбирают
`restricted`, где мало имени статуса (человек может быть и в канале, и уже вышедшим).

⚠️ Апдейты приходят по ВСЕМ чатам, где бот админ (ещё и группа обсуждений), поэтому чужие
отсекаются по id канала — иначе комментаторы группы попадали бы в статистику канала.

Бот админ канала (он туда постит), так что право на эти апдейты у него есть; отдельного
`allowed_updates` не требуется — aiogram выводит список из зарегистрированных хендлеров
(`dp.resolve_used_update_types()` в `main`), и `chat_member` появляется в нём сам.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import JOIN_TRANSITION, LEAVE_TRANSITION, ChatMemberUpdatedFilter
from aiogram.types import ChatMemberUpdated
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.application.ports.repositories import ChannelMemberEventRepository
from app.config.settings import AppConfig
from app.domain.analytics.events import ChannelMemberChange

router = Router(name="channel_members")


async def _record(
    event: ChatMemberUpdated,
    config: AppConfig,
    members: ChannelMemberEventRepository,
    change: ChannelMemberChange,
) -> None:
    """Записать движение, если оно про НАШ канал (запись fail-open — см. порт)."""
    channel_id = config.bot.public_channel_id
    if not channel_id or event.chat.id != channel_id:
        return
    await members.add(event.new_chat_member.user.id, change)


@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
@inject
async def joined(
    event: ChatMemberUpdated,
    config: FromDishka[AppConfig],
    members: FromDishka[ChannelMemberEventRepository],
) -> None:
    await _record(event, config, members, ChannelMemberChange.JOIN)


@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=LEAVE_TRANSITION))
@inject
async def left(
    event: ChatMemberUpdated,
    config: FromDishka[AppConfig],
    members: FromDishka[ChannelMemberEventRepository],
) -> None:
    await _record(event, config, members, ChannelMemberChange.LEAVE)
