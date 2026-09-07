"""Порт группы обсуждений канала (комментарии под постами).

Отдельно от `ChannelPublisher` (ISP): канал — витрина, куда бот ПИШЕТ; группа — место, где
бот ЧИТАЕТ чужое и убирает лишнее. Единственный сценарий сейчас — жұмбақ: ответ человека
записан → комментарий удаляется (чтобы не спойлерить остальным) → в ветку уходит короткое
подтверждение. Группа не настроена (`BOT_DISCUSSION_GROUP_ID=0`) → оба метода no-op.
Исключений не бросает — по тем же причинам, что публикатор.
"""

from __future__ import annotations

from typing import Protocol


class DiscussionGroup(Protocol):
    async def delete_message(self, message_id: int) -> bool: ...

    async def reply_in_thread(self, thread_message_id: int, text: str) -> bool:
        """Сообщение в ветку комментариев поста (`message_thread_id` = id авто-форварда)."""
        ...
