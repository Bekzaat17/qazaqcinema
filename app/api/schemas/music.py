"""DTO музыки. `telegram_file_id` наружу не уходит: слушать — по подписанной ссылке."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.application.ports.music import PlaylistAddOutcome
from app.application.services.music_catalog_service import MusicHome
from app.application.services.music_media_service import streamable
from app.application.services.playlist_service import PlaylistView
from app.domain.music.playlist import Playlist
from app.domain.music.stream import stream_expiry, stream_signature
from app.domain.music.track import Track

_BASE = "/api/music"


def cover_url(track_id: int) -> str:
    return f"{_BASE}/tracks/{track_id}/cover"


class TrackOut(BaseModel):
    id: int
    title: str
    performer: str
    duration_sec: int
    cover_url: str | None = None
    # None — файл тяжелее предела Bot API: такой трек слушают только в чате с ботом.
    stream_url: str | None = None
    play_count: int = 0
    saves_count: int = 0

    @classmethod
    def from_domain(cls, track: Track, key: bytes, now: datetime) -> TrackOut:
        if track.id is None:
            raise ValueError("трек без id не может быть отдан наружу")
        stream = None
        if streamable(track.file_size):
            expires = stream_expiry(now)
            signature = stream_signature(key, track.id, expires)
            stream = f"{_BASE}/stream/{track.id}?e={expires}&s={signature}"
        return cls(
            id=track.id,
            title=track.title,
            performer=track.performer,
            duration_sec=track.duration_sec,
            cover_url=cover_url(track.id) if track.cover_file_id else None,
            stream_url=stream,
            play_count=track.play_count,
            saves_count=track.saves_count,
        )


def tracks_out(tracks: list[Track], key: bytes, now: datetime) -> list[TrackOut]:
    return [TrackOut.from_domain(track, key, now) for track in tracks]


class RequestOut(BaseModel):
    query: str
    votes: int


class MusicHomeOut(BaseModel):
    recent: list[TrackOut]
    popular: list[TrackOut]
    requests: list[RequestOut]

    @classmethod
    def from_domain(cls, home: MusicHome, key: bytes, now: datetime) -> MusicHomeOut:
        return cls(
            recent=tracks_out(home.recent, key, now),
            popular=tracks_out(home.popular, key, now),
            requests=[RequestOut(query=r.query, votes=r.votes) for r in home.requests],
        )


class PlaylistOut(BaseModel):
    id: int
    title: str
    track_count: int
    covers: list[str]
    share_url: str
    is_own: bool = True

    @classmethod
    def from_domain(cls, playlist: Playlist, bot_username: str, viewer_id: int) -> PlaylistOut:
        if playlist.id is None:
            raise ValueError("плейлист без id не может быть отдан наружу")
        return cls(
            id=playlist.id,
            title=playlist.title,
            track_count=playlist.track_count,
            covers=[cover_url(track_id) for track_id in playlist.cover_track_ids],
            share_url=f"https://t.me/{bot_username}?startapp=pl_{playlist.share_code}",
            is_own=playlist.owner_id == viewer_id,
        )


class PlaylistDetailOut(PlaylistOut):
    tracks: list[TrackOut]

    @classmethod
    def from_view(
        cls, view: PlaylistView, bot_username: str, viewer_id: int, key: bytes, now: datetime
    ) -> PlaylistDetailOut:
        base = PlaylistOut.from_domain(view.playlist, bot_username, viewer_id)
        return cls(**base.model_dump(), tracks=tracks_out(view.tracks, key, now))


class PlaylistIn(BaseModel):
    title: str = Field(default="", max_length=200)


class PlaylistAddOut(BaseModel):
    status: PlaylistAddOutcome


class IdsOut(BaseModel):
    ids: list[int]


class MusicRequestIn(BaseModel):
    query: str = Field(min_length=1, max_length=200)


class MusicRequestOut(BaseModel):
    votes: int


class SendOut(BaseModel):
    status: Literal["sent"]
    count: int
