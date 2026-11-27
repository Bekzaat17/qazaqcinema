"""Ссылки на музыку в payload бота и Mini App: `music`, `t_<id>`, `pl_<код>`.

Тот же формат с необязательной меткой источника, что у фильмов (`ch-t_42`): хит-парад
в канале и пересланный трек должны открывать музыку, а не главную кинотеатра.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_LINK = re.compile(r"^(?:[a-z]{1,16}-)?(?:(music)|t_(\d+)|pl_([A-Za-z0-9_-]{4,16}))$")


@dataclass(frozen=True, slots=True)
class MusicLink:
    track_id: int | None = None
    playlist_code: str | None = None


def parse_music_link(payload: str | None) -> MusicLink | None:
    """Разобрать payload; `None` — ссылка не про музыку."""
    match = _LINK.match(payload or "")
    if match is None:
        return None
    track, playlist = match.group(2), match.group(3)
    return MusicLink(int(track) if track else None, playlist)
