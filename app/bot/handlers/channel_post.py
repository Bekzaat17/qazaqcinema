"""Автонаполнение каталога: видео-пост в секретном канале → фильм в БД.

Скелет. Реализация — PLAN (фаза «бот»):
  1. Отфильтровать посты только из BOT_ARCHIVE_CHANNEL_ID.
  2. parsed = parse_caption(message.caption)  # CaptionParseError → DM админу об ошибке.
  3. saved = await ingestion.ingest(parsed, message.video.file_id)
  4. DM админу: «Фильм «{title}» добавлен. ID: {id}».
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

router = Router(name="channel_post")


@router.channel_post(F.video)
async def handle_archive_video(message: Message) -> None:
    return  # TODO(PLAN: бот): парсинг подписи + MovieIngestionService.ingest
