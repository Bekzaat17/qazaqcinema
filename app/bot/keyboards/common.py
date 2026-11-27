"""Общие клавиатуры бота."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


def music_url(url: str, track_id: int | None = None, playlist_code: str | None = None) -> str:
    """URL Mini App сразу на музыке (и на треке/плейлисте) — в query, как у фильма."""
    sep = "&" if "?" in url else "?"
    target = f"{url}{sep}app=music"
    if track_id is not None:
        target += f"&t={track_id}"
    if playlist_code is not None:
        target += f"&pl={playlist_code}"
    return target


MUSIC_RENAME_PREFIX = "mrename:"


def music_keyboard(
    url: str,
    track_id: int | None = None,
    playlist_code: str | None = None,
    *,
    rename: bool = False,
) -> InlineKeyboardMarkup:
    """Кнопка «🎧 Музыканы ашу» — Mini App сразу в музыкальном разделе.

    `rename` — под ответом о новом треке: приславший может сразу поправить название,
    если теги файла были пустыми или кривыми.
    """
    rows = [[
        InlineKeyboardButton(
            text="🎧 Музыканы ашу",
            web_app=WebAppInfo(url=music_url(url, track_id, playlist_code)),
        )
    ]]
    if rename and track_id is not None:
        rows.append([InlineKeyboardButton(
            text="✏️ Атын түзету", callback_data=f"{MUSIC_RENAME_PREFIX}{track_id}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
