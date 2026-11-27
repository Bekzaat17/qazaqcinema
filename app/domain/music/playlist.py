"""Плейлисты слушателей: ограничения и правила общего доступа по ссылке."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime

TITLE_MAX = 64
# Пределы — защита от случайного или злонамеренного раздувания, а не тарифные лимиты.
MAX_PLAYLISTS_PER_USER = 100
MAX_TRACKS_PER_PLAYLIST = 500
DEFAULT_TITLE = "Жаңа плейлист"
# Короткий непредсказуемый код для ссылки `startapp=pl_<code>`: id в ссылке позволил бы
# перебором открыть чужие плейлисты, а длинный токен не влезает в лимит start-параметра.
SHARE_CODE_BYTES = 6


@dataclass(slots=True)
class Playlist:
    owner_id: int
    title: str
    share_code: str
    track_count: int = 0
    # Виден всем в «Тыңдаушылардың плейлистері»; по умолчанию — только по ссылке.
    is_public: bool = False
    # Сколько людей сохранили себе копию — порядок публичных плейлистов.
    saves_count: int = 0
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


def playlist_title(raw: str | None) -> str:
    title = " ".join((raw or "").split())[:TITLE_MAX].strip()
    return title or DEFAULT_TITLE


def new_share_code() -> str:
    return secrets.token_urlsafe(SHARE_CODE_BYTES)


