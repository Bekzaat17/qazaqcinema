"""DTO музыки. `telegram_file_id` наружу не уходит: слушают в чате с ботом, как фильмы."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.application.ports.music import PlaylistAddOutcome
from app.application.services.music_catalog_service import (
    CollectionView,
    MusicHome,
    TrackDetails,
)
from app.application.services.playlist_service import PlaylistView
from app.domain.music.playlist import Playlist
from app.domain.music.seo import artist_slug
from app.domain.music.track import Track


class TrackOut(BaseModel):
    id: int
    title: str
    performer: str
    duration_sec: int
    play_count: int = 0
    saves_count: int = 0

    @classmethod
    def from_domain(cls, track: Track) -> TrackOut:
        if track.id is None:
            raise ValueError("трек без id не может быть отдан наружу")
        return cls(
            id=track.id,
            title=track.title,
            performer=track.performer,
            duration_sec=track.duration_sec,
            play_count=track.play_count,
            saves_count=track.saves_count,
        )


def tracks_out(tracks: list[Track]) -> list[TrackOut]:
    return [TrackOut.from_domain(track) for track in tracks]


class RequestOut(BaseModel):
    query: str
    votes: int


class MusicHomeOut(BaseModel):
    recent: list[TrackOut]
    popular: list[TrackOut]
    requests: list[RequestOut]

    @classmethod
    def from_domain(cls, home: MusicHome) -> MusicHomeOut:
        return cls(
            recent=tracks_out(home.recent),
            popular=tracks_out(home.popular),
            requests=[RequestOut(query=r.query, votes=r.votes) for r in home.requests],
        )


class PlaylistOut(BaseModel):
    id: int
    title: str
    track_count: int
    share_code: str
    share_url: str
    is_own: bool = True
    is_public: bool = False
    saves_count: int = 0

    @classmethod
    def from_domain(cls, playlist: Playlist, bot_username: str, viewer_id: int) -> PlaylistOut:
        if playlist.id is None:
            raise ValueError("плейлист без id не может быть отдан наружу")
        return cls(
            id=playlist.id,
            title=playlist.title,
            track_count=playlist.track_count,
            share_code=playlist.share_code,
            share_url=f"https://t.me/{bot_username}?startapp=pl_{playlist.share_code}",
            is_own=playlist.owner_id == viewer_id,
            is_public=playlist.is_public,
            saves_count=playlist.saves_count,
        )


class PlaylistDetailOut(PlaylistOut):
    tracks: list[TrackOut]

    @classmethod
    def from_view(cls, view: PlaylistView, bot_username: str, viewer_id: int) -> PlaylistDetailOut:
        base = PlaylistOut.from_domain(view.playlist, bot_username, viewer_id)
        return cls(**base.model_dump(), tracks=tracks_out(view.tracks))


class TrackDetailOut(BaseModel):
    """Страница трека в Mini App: цифры и куда идти дальше."""

    track: TrackOut
    artist_slug: str
    listeners: int
    playlists_count: int
    saves: int
    by_artist: list[TrackOut]
    similar: list[TrackOut]
    playlists: list[PlaylistOut]

    @classmethod
    def from_domain(
        cls, details: TrackDetails, bot_username: str, viewer_id: int
    ) -> TrackDetailOut:
        return cls(
            track=TrackOut.from_domain(details.track),
            artist_slug=artist_slug(details.track.performer),
            listeners=details.stats.listeners,
            playlists_count=details.stats.playlists,
            saves=details.stats.saves,
            by_artist=tracks_out(details.by_artist),
            similar=tracks_out(details.similar),
            playlists=[
                PlaylistOut.from_domain(p, bot_username, viewer_id) for p in details.playlists
            ],
        )


class ArtistOut(BaseModel):
    name: str
    slug: str
    tracks: list[TrackOut]


class PlaylistIn(BaseModel):
    title: str = Field(default="", max_length=200)
    # Сразу с треками — «Өзіме сақтау» у готовой подборки.
    track_ids: list[int] = Field(default_factory=list, max_length=500)


class PlaylistPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    is_public: bool | None = None


class CollectionOut(BaseModel):
    key: str
    title: str
    subtitle: str
    track_count: int
    # Первые исполнители — подпись карточки («Қайрат Нұртас, Ninety One және т.б.»).
    performers: list[str]


class CollectionDetailOut(CollectionOut):
    tracks: list[TrackOut]


def collection_out(view: CollectionView) -> CollectionOut:
    performers = list(dict.fromkeys(track.performer for track in view.tracks))[:3]
    return CollectionOut(
        key=view.collection.kind.value,
        title=view.collection.title,
        subtitle=view.collection.subtitle,
        track_count=len(view.tracks),
        performers=performers,
    )


def collection_detail(view: CollectionView) -> CollectionDetailOut:
    return CollectionDetailOut(**collection_out(view).model_dump(), tracks=tracks_out(view.tracks))


class PlaylistAddOut(BaseModel):
    status: PlaylistAddOutcome


class TrackIdsIn(BaseModel):
    """Упорядоченный список треков: в этом порядке они уйдут в чат и так их сыграет Telegram."""

    track_ids: list[int] = Field(min_length=1, max_length=500)


class IdsOut(BaseModel):
    ids: list[int]


class MusicRequestIn(BaseModel):
    query: str = Field(min_length=1, max_length=200)


class MusicRequestOut(BaseModel):
    votes: int


class SendOut(BaseModel):
    status: Literal["sent"]
    count: int
