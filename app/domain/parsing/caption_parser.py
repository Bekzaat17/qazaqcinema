"""Парсер подписи видео-поста из секретного канала.

Формат подписи (ключи в любом порядке, значение тянется до следующего ключа):

    #title Арыстан Патша / Король Лев
    #category disney
    #year 1994
    #rating 8.5
    #poster https://link/lion_king.jpg
    #desc Симба есімді кішкентай арыстанның тақ үшін күресі туралы...

Чистая доменная функция: на вход текст, на выход `ParsedMovie` либо `CaptionParseError`.
Набор ключей задаётся одним кортежем — добавить ключ можно точечно (Open/Closed).
"""

from __future__ import annotations

import re

from app.domain.parsing.parsed_movie import ParsedMovie

KNOWN_KEYS: tuple[str, ...] = ("title", "category", "year", "rating", "poster", "desc")
REQUIRED_KEYS: tuple[str, ...] = ("title", "category", "poster", "desc")

_KEY_RE = re.compile(r"#(" + "|".join(KNOWN_KEYS) + r")\b", re.IGNORECASE)
# Постер админ может вставить как markdown-ссылку: [текст](url)
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\((?P<url>[^)]+)\)")


class CaptionParseError(ValueError):
    """Подпись не распознана как описание фильма."""


def parse_caption(text: str | None) -> ParsedMovie:
    if not text:
        raise CaptionParseError("пустая подпись")

    matches = list(_KEY_RE.finditer(text))
    if not matches:
        raise CaptionParseError("не найдено ни одного ключа (#title, #category, …)")

    fields: dict[str, str] = {}
    for index, match in enumerate(matches):
        key = match.group(1).lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        fields[key] = text[start:end].strip()

    missing = [key for key in REQUIRED_KEYS if not fields.get(key)]
    if missing:
        raise CaptionParseError("отсутствуют обязательные ключи: " + ", ".join(missing))

    return ParsedMovie(
        title=fields["title"],
        category=fields["category"].lower(),
        description=fields["desc"],
        poster_url=_clean_url(fields["poster"]),
        year=_to_int(fields.get("year")),
        rating=_to_float(fields.get("rating")),
    )


def _clean_url(raw: str) -> str:
    md = _MD_LINK_RE.search(raw)
    return md.group("url").strip() if md else raw.strip()


def _to_int(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(raw.strip())
    except ValueError:
        return None


def _to_float(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return float(raw.strip().replace(",", "."))
    except ValueError:
        return None
