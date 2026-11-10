"""Общие клавиатуры бота."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


def quest_keyboard(url: str) -> InlineKeyboardMarkup:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query["game"] = "quest"
    target = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏡 QazaqQuest ойнау", web_app=WebAppInfo(url=target)),
    ]])


def webapp_keyboard(url: str) -> InlineKeyboardMarkup:
    """Кнопка открытия Web App (🍿 Кинотеатрды ашу)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🍿 Кинотеатрды ашу", web_app=WebAppInfo(url=url))]
        ]
    )


def movie_keyboard(url: str, movie_id: int) -> InlineKeyboardMarkup:
    """Кнопка, открывающая Web App сразу на карточке фильма.

    Фильм — в query (`?m=<id>`), а не в хэше: в хэш Telegram дописывает `tgWebAppData`,
    и `#m42` превращался бы в `#m42&tgWebAppData=…`.
    """
    sep = "&" if "?" in url else "?"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Көру", web_app=WebAppInfo(url=f"{url}{sep}m={movie_id}"))]
        ]
    )
