"""Защищённая выдача видео через inline-режим.

Скелет. Реализация — PLAN (фаза «бот»):
  1. Распарсить query вида 'movie_<id>'.
  2. Проверить активную подписку юзера (User.has_active_access). Нет — пустая выдача/подсказка.
  3. movie = await catalog.get_movie(id); вернуть InlineQueryResultCachedVideo(
        video_file_id=movie.telegram_file_id, ..., protect_content=True).
Флаг protect_content=True — запрет скачивания/пересылки/записи экрана.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.types import InlineQuery

router = Router(name="inline_query")

MOVIE_PREFIX = "movie_"


@router.inline_query()
async def handle_inline_query(query: InlineQuery) -> None:
    return  # TODO(PLAN: бот): проверка подписки + защищённая inline-выдача видео
