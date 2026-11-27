"""Трек общего каталога и правила разбора того, что прислали в бота.

⚠️ Сервер хранит о треке только сведения и `file_id` Telegram — как у фильмов. Самого
файла (и обложки) на диске нет: аудио живёт в Telegram и уходит слушателю в чат.

Каталог наполняют сами слушатели: аудио, присланное или пересланное боту, сразу
попадает в общий список. Поэтому названия здесь приходят «как есть» — из ID3-тегов,
а чаще из имени файла вида `Artist - Title (www.site.kz).mp3`. Чистка этих хвостов —
правило продукта (что увидит слушатель), а не деталь бота, и живёт в домене.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

TITLE_MAX = 128
PERFORMER_MAX = 128
# Короче — это звонок, звук уведомления или обрывок голосового, а не песня.
MIN_DURATION_SEC = 10
UNKNOWN_PERFORMER = "Белгісіз орындаушы"
UNTITLED = "Атаусыз трек"

# Хвосты, которые музыкальные каналы и сайты вшивают в имя файла и в теги.
_JUNK = (
    re.compile(r"\((?:www\.|https?://|@)[^)]*\)", re.IGNORECASE),
    re.compile(r"\[(?:www\.|https?://|@)[^\]]*\]", re.IGNORECASE),
    re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE),
    re.compile(r"(?<![\w.])@\w{3,}"),
    # Только «скачать»: английские download/free бывают частью настоящего названия.
    re.compile(r"\bскачать\b.*$", re.IGNORECASE),
)
_EXTENSION = re.compile(r"\.(?:mp3|m4a|aac|ogg|oga|opus|flac|wav|wma)$", re.IGNORECASE)
_TRACK_NUMBER = re.compile(r"^\s*\d{1,3}\s*[.)\-_]\s*")
_SEPARATOR = re.compile(r"\s+[-–—]\s+")


@dataclass(frozen=True, slots=True)
class AudioUpload:
    """Аудио из сообщения в боте — всё, что Telegram о нём сообщил."""

    file_id: str
    file_unique_id: str
    duration_sec: int
    title: str | None = None
    performer: str | None = None
    file_name: str | None = None
    file_size: int | None = None
    mime_type: str | None = None


@dataclass(frozen=True, slots=True)
class TrackName:
    title: str
    performer: str


@dataclass(slots=True)
class Track:
    title: str
    performer: str
    duration_sec: int
    telegram_file_id: str
    file_unique_id: str
    uploader_id: int
    file_size: int | None = None
    mime_type: str | None = None
    archive_message_id: int | None = None
    play_count: int = 0
    saves_count: int = 0
    # Скрыт админом (жалоба, правообладатель): из каталога пропал, повторно не заливается.
    is_hidden: bool = False
    id: int | None = None
    created_at: datetime | None = None


def _clean(raw: str | None, limit: int) -> str:
    if not raw:
        return ""
    text = raw.replace("_", " ")
    for pattern in _JUNK:
        text = pattern.sub(" ", text)
    text = " ".join(text.split()).strip(" -–—.,|")
    return text[:limit].strip()


def track_name(upload: AudioUpload) -> TrackName:
    """Название и исполнитель: теги, если они есть, иначе разбор имени файла.

    Имя файла `Artist - Title.mp3` разбирается по первому тире, окружённому пробелами:
    дефис внутри слова («Қара-Торғай») разделителем не считается.
    """
    title = _clean(upload.title, TITLE_MAX)
    performer = _clean(upload.performer, PERFORMER_MAX)
    if title and performer:
        return TrackName(title, performer)
    stem = _EXTENSION.sub("", upload.file_name or "")
    stem = _TRACK_NUMBER.sub("", stem.replace("_", " "))
    parts = _SEPARATOR.split(stem, maxsplit=1)
    if len(parts) == 2:
        file_performer, file_title = _clean(parts[0], PERFORMER_MAX), _clean(parts[1], TITLE_MAX)
    else:
        file_performer, file_title = "", _clean(stem, TITLE_MAX)
    return TrackName(
        title or file_title or UNTITLED,
        performer or file_performer or UNKNOWN_PERFORMER,
    )


def is_music(upload: AudioUpload) -> bool:
    """Похоже ли присланное на трек, а не на звонок или кусок голосового."""
    return upload.duration_sec >= MIN_DURATION_SEC


def search_key(text: str) -> str:
    """Ключ сравнения запросов: регистр, пунктуация и лишние пробелы не важны."""
    folded = re.sub(r"[^\w\s]", " ", text.casefold())
    return " ".join(folded.split())
