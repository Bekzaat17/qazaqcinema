"""«Менің музыкам» — личная коллекция из общего каталога («добавить к себе»)."""

from __future__ import annotations

from datetime import datetime

from app.application.ports.music import LibraryRepository, TrackRepository
from app.domain.music.track import Track

LIBRARY_PAGE_MAX = 200


class MusicLibraryService:
    def __init__(self, library: LibraryRepository, tracks: TrackRepository) -> None:
        self._library = library
        self._tracks = tracks

    async def save(self, user_id: int, track_id: int, now: datetime) -> bool:
        """Забрать трек себе. False — такого трека нет (повтор не ошибка)."""
        if await self._tracks.get(track_id) is None:
            return False
        await self._library.add(user_id, track_id, now)
        return True

    async def remove(self, user_id: int, track_id: int) -> None:
        await self._library.remove(user_id, track_id)

    async def tracks(self, user_id: int, limit: int, offset: int) -> list[Track]:
        return await self._library.list_for_user(
            user_id, min(max(limit, 1), LIBRARY_PAGE_MAX), max(offset, 0)
        )

    async def ids(self, user_id: int) -> list[int]:
        return await self._library.list_ids(user_id)
