"""Inline-режим: НЕ отдаёт видео.

`InlineQueryResult*` не поддерживают `protect_content` (проверено на aiogram 3.x), а
незащищённое видео нарушило бы ядро безопасности продукта. Поэтому inline показывает
лишь кнопку открыть Web App / оформить подписку, а защищённую выдачу делает API
`/play` → `PlaybackService` → `send_video(protect_content=True)`.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultsButton, WebAppInfo
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.config.settings import AppConfig

router = Router(name="inline_query")


def _open_app_button(webapp_url: str) -> InlineQueryResultsButton:
    text = "QazaqCinema-ны ашу"
    # web_app требует https-URL; если он не настроен (dev) — deep-link в бота,
    # иначе answerInlineQuery упадёт с BadRequest.
    if webapp_url.startswith("https://"):
        return InlineQueryResultsButton(text=text, web_app=WebAppInfo(url=webapp_url))
    return InlineQueryResultsButton(text=text, start_parameter="open")


@router.inline_query()
@inject
async def handle_inline_query(query: InlineQuery, config: FromDishka[AppConfig]) -> None:
    # Пустая выдача + кнопка. cache_time=0 + is_personal: ничего не кешируем по чужим
    # подпискам (задел на случай будущих персональных результатов).
    await query.answer(
        results=[],
        cache_time=0,
        is_personal=True,
        button=_open_app_button(config.bot.webapp_url),
    )
