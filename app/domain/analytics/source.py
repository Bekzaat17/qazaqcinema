"""Откуда пришёл человек: метка источника в deep-link.

Ссылка в кинотеатр несёт payload — `start=` у бота (основной путь, см. `movie_start_url`)
и `startapp=` у старых прямых ссылок в Mini App. Формат:
`<источник>-m_<id>` (ссылка на фильм) или просто `<источник>`:
  • `seo` — сайт (кнопка на странице фильма, подвал);
  • `ch`  — пост в канале;
  • `web` — шторка «Ботты ашу» в самом кинотеатре.

Метка уходит в `meta` событий `open` и `start` — так видно, какой канал приводит людей,
без отдельной таблицы: первое `open` человека с меткой и есть его первое касание.

Старые ссылки без метки (`m_<id>`) продолжают открывать фильм и считаются `link`: до метки
сайт и канал слали одинаковое, и различить их задним числом нечем. Без payload (кнопка в
чате бота, меню) источника нет — это возврат, а не приход.
"""

from __future__ import annotations

import re

SEO = "seo"
CHANNEL = "ch"
UNTAGGED = "link"

# Имя источника — латиница в нижнем регистре, как и допускает Telegram в payload.
_TAGGED = re.compile(r"^([a-z]{1,16})(?:-|$)")
_MOVIE = re.compile(r"^(?:[a-z]{1,16}-)?m_?(\d+)$")


def movie_link_payload(source: str, movie_id: int) -> str:
    """Payload ссылки на фильм: `seo-m_42`."""
    return f"{source}-m_{movie_id}"


def movie_start_url(bot_username: str, source: str, movie_id: int) -> str:
    """Ссылка на фильм через ЧАТ бота: `t.me/<bot>?start=ch-m_42`.

    Именно `start=`, а не `startapp=`. Mini App, открытая прямой ссылкой, не может увести
    человека в чат своего же бота (клиент игнорирует `openTelegramLink` на него), а видео
    приходит как раз туда. Через `/start` человек сначала оказывается в чате, бот отвечает
    кнопкой, и кинотеатр открывается уже ИЗ ЧАТА — после «Көру» он просто закрывается, и
    под ним тот самый чат с видео. Цена — один тап; заодно /start открывает боту личку.
    """
    return f"https://t.me/{bot_username}?start={movie_link_payload(source, movie_id)}"


def link_source(payload: str | None) -> str | None:
    """Источник из payload; `None` — payload нет (заход из чата бота)."""
    if not payload:
        return None
    match = _TAGGED.match(payload)
    return match.group(1) if match else UNTAGGED


def link_movie_id(payload: str | None) -> int | None:
    """ID фильма из payload — с меткой источника или без неё."""
    match = _MOVIE.match(payload or "")
    return int(match.group(1)) if match else None
