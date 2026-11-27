"""Файлы для прослушивания прямо в Mini App: аудио и обложки из Telegram на диске."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.application.ports.music import AudioFiles, TrackRepository

# ⚠️ Предел Bot API на скачивание файла ботом. Трек тяжелее слушают только в чате.
STREAM_MAX_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class AudioFile:
    path: Path
    mime_type: str


def streamable(file_size: int | None) -> bool:
    """Можно ли слушать в Mini App. Размер неизвестен — пробуем: скачивание само скажет."""
    return file_size is None or file_size <= STREAM_MAX_BYTES


class MusicMediaService:
    def __init__(self, tracks: TrackRepository, files: AudioFiles) -> None:
        self._tracks = tracks
        self._files = files

    async def audio(self, track_id: int) -> AudioFile | None:
        track = await self._tracks.get(track_id)
        if track is None or not streamable(track.file_size):
            return None
        path = await self._files.audio(track.telegram_file_id, track.file_unique_id)
        if path is None:
            return None
        return AudioFile(path, track.mime_type or "audio/mpeg")

    async def cover(self, track_id: int) -> Path | None:
        track = await self._tracks.get(track_id)
        if track is None or track.cover_file_id is None:
            return None
        return await self._files.cover(track.cover_file_id, track.file_unique_id)

    def prune(self, max_bytes: int) -> int:
        return self._files.prune(max_bytes)
