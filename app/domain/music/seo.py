"""Адреса и тексты SEO-страниц музыки — данные и чистые функции, без шаблонов.

Песни ищут в Google по-казахски, по-русски и латиницей («Қайрат Нұртас Ауру текст»,
«кайрат нуртас ауру слушать», «kairat nurtas auru mp3»), поэтому формулировки спроса —
строки здесь, а не в шаблоне. Ведущий id трека — источник правды URL, хвост — для людей.
"""

from __future__ import annotations

import re

from app.domain.music.search import fold
from app.domain.seo.slug import slugify

MUSIC_PATH = "/music"
TRACK_PREFIX = "/music/"
ARTIST_PREFIX = "/music/artist/"
PLAYLIST_PREFIX = "/music/playlist/"

_LEADING_ID = re.compile(r"^(\d+)(?:-|$)")

# Как люди ищут песню, кроме самого названия (подставляются в keywords и описание).
TRACK_QUERIES = ("тыңдау", "слушать онлайн", "mp3", "Telegram")
ARTIST_QUERIES = ("әндері", "песни", "барлық әндері", "слушать все песни")


def track_path(track_id: int, performer: str, title: str) -> str:
    tail = slugify(f"{performer} {title}")
    return f"{TRACK_PREFIX}{track_id}-{tail}" if tail else f"{TRACK_PREFIX}{track_id}"


def track_id_from_slug(slug: str) -> int | None:
    match = _LEADING_ID.match(slug)
    return int(match.group(1)) if match else None


def artist_key(performer: str) -> str:
    """Ключ исполнителя — тот же `fold`, что и в поиске: «Қайрат» = «Кайрат»."""
    return fold(performer)


def artist_slug(performer: str) -> str:
    return artist_key(performer).replace(" ", "-")


def artist_path(performer: str) -> str:
    return f"{ARTIST_PREFIX}{artist_slug(performer)}"


def artist_key_from_slug(slug: str) -> str:
    """Слаг из адреса → ключ. Через `fold`: «qairat-nurtas» и «kairat-nurtas» — один
    исполнитель, а страница сама ответит 301 на канонический адрес."""
    return fold(slug.replace("-", " "))


def playlist_path(share_code: str) -> str:
    return f"{PLAYLIST_PREFIX}{share_code}"


def track_title_tag(performer: str, title: str) -> str:
    return f"{performer} — {title} тыңдау, слушать | QazaqMusic"[:70]


def track_description(performer: str, title: str, listeners: int) -> str:
    heard = f" {listeners} адам тыңдады." if listeners else ""
    text = (
        f"{performer} — {title}: Telegram-да тегін тыңдаңыз, экран сөніп тұрса да."
        f"{heard} Слушать песню онлайн бесплатно в Telegram."
    )
    return text[:160]


def artist_title_tag(name: str, count: int) -> str:
    return f"{name} — барлық әндері ({count}) тыңдау | QazaqMusic"[:70]


def artist_description(name: str, count: int) -> str:
    return (
        f"{name}: {count} ән бір жерде. Telegram-да тегін тыңдаңыз, плейлист жинаңыз. "
        f"Все песни {name} слушать онлайн."
    )[:160]


def iso_duration(seconds: int) -> str:
    """Длительность для schema.org (`PT3M34S`)."""
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    return f"PT{minutes}M{secs}S"


def clock(seconds: int) -> str:
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def cover_gradient(seed: str) -> str:
    """Тот же цвет плитки, что в Mini App (`web/src/music/format.coverGradient`)."""
    value = 0
    for char in seed:
        value = (value * 31 + ord(char)) & 0xFFFFFFFF
    signed = value - (1 << 32) if value >= 1 << 31 else value
    hue = abs(signed) % 360
    second = (hue + 48) % 360
    return f"linear-gradient(135deg, hsl({hue} 70% 46%), hsl({second} 75% 30%))"


def initials(text: str) -> str:
    letters = [word[0].upper() for word in text.split()[:2] if word]
    return "".join(letters) or "♪"
