"""Плейлисты: свои — правит только владелец, чужие — открываются по коду из ссылки."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.ports.music import PlaylistAddOutcome, PlaylistRepository, TrackRepository
from app.domain.music.playlist import (
    MAX_PLAYLISTS_PER_USER,
    MAX_TRACKS_PER_PLAYLIST,
    Playlist,
    new_share_code,
    playlist_title,
)
from app.domain.music.track import Track


@dataclass(frozen=True, slots=True)
class PlaylistView:
    playlist: Playlist
    tracks: list[Track]


class PlaylistService:
    def __init__(self, playlists: PlaylistRepository, tracks: TrackRepository) -> None:
        self._playlists = playlists
        self._tracks = tracks

    async def _owned(self, owner_id: int, playlist_id: int) -> Playlist | None:
        playlist = await self._playlists.get(playlist_id)
        if playlist is None or playlist.owner_id != owner_id:
            # Чужой и несуществующий неотличимы: id плейлистов не должны угадываться.
            return None
        return playlist

    async def _view(self, playlist: Playlist) -> PlaylistView:
        assert playlist.id is not None
        ids = await self._playlists.track_ids(playlist.id)
        return PlaylistView(playlist, await self._tracks.list_by_ids(ids))

    async def create(self, owner_id: int, title: str | None, now: datetime) -> Playlist | None:
        """Новый пустой плейлист. None — достигнут предел плейлистов у человека."""
        if await self._playlists.count_for_owner(owner_id) >= MAX_PLAYLISTS_PER_USER:
            return None
        return await self._playlists.create(Playlist(
            owner_id=owner_id,
            title=playlist_title(title),
            share_code=new_share_code(),
            created_at=now,
        ))

    async def list_mine(self, owner_id: int) -> list[Playlist]:
        return await self._playlists.list_for_owner(owner_id)

    async def open(self, owner_id: int, playlist_id: int) -> PlaylistView | None:
        playlist = await self._owned(owner_id, playlist_id)
        return await self._view(playlist) if playlist else None

    async def shared(self, share_code: str) -> PlaylistView | None:
        playlist = await self._playlists.by_share_code(share_code)
        return await self._view(playlist) if playlist else None

    async def rename(self, owner_id: int, playlist_id: int, title: str, now: datetime) -> bool:
        if await self._owned(owner_id, playlist_id) is None:
            return False
        await self._playlists.rename(playlist_id, playlist_title(title), now)
        return True

    async def delete(self, owner_id: int, playlist_id: int) -> bool:
        if await self._owned(owner_id, playlist_id) is None:
            return False
        await self._playlists.delete(playlist_id)
        return True

    async def add_track(
        self, owner_id: int, playlist_id: int, track_id: int, now: datetime
    ) -> PlaylistAddOutcome | None:
        """None — плейлиста или трека нет (для владельца это одно и то же «не найдено»)."""
        if await self._owned(owner_id, playlist_id) is None:
            return None
        if await self._tracks.get(track_id) is None:
            return None
        return await self._playlists.add_track(
            playlist_id, track_id, now, MAX_TRACKS_PER_PLAYLIST
        )

    async def remove_track(
        self, owner_id: int, playlist_id: int, track_id: int, now: datetime
    ) -> bool:
        if await self._owned(owner_id, playlist_id) is None:
            return False
        await self._playlists.remove_track(playlist_id, track_id, now)
        return True

    async def save_shared(self, owner_id: int, share_code: str, now: datetime) -> Playlist | None:
        """Сохранить чужой плейлист себе копией.

        Копия, а не подписка на оригинал: автор может удалить или переделать свой
        плейлист, а у того, кто его сохранил, музыка пропадать не должна.
        """
        source = await self._playlists.by_share_code(share_code)
        if source is None or source.id is None:
            return None
        if source.owner_id == owner_id:
            return source
        copy = await self.create(owner_id, source.title, now)
        if copy is None or copy.id is None:
            return None
        ids = await self._playlists.track_ids(source.id)
        await self._playlists.add_tracks(copy.id, ids, now, MAX_TRACKS_PER_PLAYLIST)
        return await self._playlists.get(copy.id)
