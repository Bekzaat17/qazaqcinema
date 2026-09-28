"""Откуда пришёл человек: метка источника в deep-link.

Ссылка в кинотеатр несёт payload — `startapp=` у Mini App и `start=` у бота. Формат:
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
