"""Интеграционные тесты музыки (Postgres): дубли, счётчики, плейлисты, запросы, хит-парад."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.application.ports.music import PlaylistAddOutcome
from app.domain.analytics.events import EventKind
from app.domain.entities.user import User
from app.domain.music.playlist import Playlist
from app.domain.music.track import Track
from app.infrastructure.db.repositories import PgUserEventRepository, PgUserRepository
from app.infrastructure.db.repositories.music import (
    PgLibraryRepository,
    PgMusicChartLog,
    PgMusicRequestRepository,
    PgPlaylistRepository,
    PgTrackRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession

_NOW = datetime(2026, 11, 27, 12, tzinfo=UTC)


def _track(unique: str, title: str = "Ауру", performer: str = "Қайрат Нұртас") -> Track:
    return Track(
        title=title, performer=performer, duration_sec=200,
        telegram_file_id=f"file-{unique}", file_unique_id=unique, uploader_id=1,
        cover_file_id=f"cover-{unique}",
    )


async def test_same_file_twice_is_one_row(session: AsyncSession) -> None:
    tracks = PgTrackRepository(session)
    first = await tracks.add(_track("u1"))
    second = await tracks.add(_track("u1", title="Другое"))
    assert first.id == second.id and second.title == "Ауру"


async def test_search_finds_performer_and_title_together_and_typos(session: AsyncSession) -> None:
    tracks = PgTrackRepository(session)
    await tracks.add(_track("u1"))
    await tracks.add(_track("u2", title="Сен", performer="Ninety One"))
    assert [t.title for t in await tracks.search("Нұртас ауру", 10)] == ["Ауру"]
    assert [t.title for t in await tracks.search("ninety", 10)] == ["Сен"]
    assert [t.title for t in await tracks.search("Кайрат", 10)] == ["Ауру"]


async def test_hidden_track_leaves_every_listing(session: AsyncSession) -> None:
    tracks = PgTrackRepository(session)
    track = await tracks.add(_track("u1"))
    assert track.id is not None
    assert await tracks.hide(track.id)
    assert not await tracks.hide(track.id)
    assert await tracks.get(track.id) is None
    assert await tracks.list_recent(10) == []
    hidden = await tracks.by_unique_id("u1")
    assert hidden is not None and hidden.is_hidden


async def test_library_toggle_moves_saves_counter_exactly_once(session: AsyncSession) -> None:
    tracks, library = PgTrackRepository(session), PgLibraryRepository(session)
    track = await tracks.add(_track("u1"))
    assert track.id is not None
    assert await library.add(5, track.id, _NOW)
    assert not await library.add(5, track.id, _NOW)
    assert (await tracks.get(track.id)).saves_count == 1  # type: ignore[union-attr]
    assert await library.list_ids(5) == [track.id]
    assert await library.remove(5, track.id)
    assert not await library.remove(5, track.id)
    assert (await tracks.get(track.id)).saves_count == 0  # type: ignore[union-attr]


async def test_playlist_keeps_order_rejects_duplicates_and_respects_limit(
    session: AsyncSession,
) -> None:
    tracks, playlists = PgTrackRepository(session), PgPlaylistRepository(session)
    ids = [(await tracks.add(_track(f"u{i}"))).id for i in range(3)]
    playlist = await playlists.create(Playlist(owner_id=5, title="Жол", share_code="abc12345",
                                               created_at=_NOW))
    assert playlist.id is not None
    for track_id in ids[:2]:
        assert track_id is not None
        assert await playlists.add_track(playlist.id, track_id, _NOW, 2) is PlaylistAddOutcome.ADDED
    assert ids[0] is not None and ids[2] is not None
    assert await playlists.add_track(playlist.id, ids[0], _NOW, 2) is PlaylistAddOutcome.DUPLICATE
    assert await playlists.add_track(playlist.id, ids[2], _NOW, 2) is PlaylistAddOutcome.FULL
    assert await playlists.track_ids(playlist.id) == ids[:2]
    stored = await playlists.by_share_code("abc12345")
    assert stored is not None and stored.track_count == 2
    assert len(stored.cover_track_ids) == 2
    assert await playlists.remove_track(playlist.id, ids[0], _NOW)
    refreshed = await playlists.get(playlist.id)
    assert refreshed is not None and refreshed.track_count == 1


async def test_request_counts_distinct_people_and_closes_on_upload(session: AsyncSession) -> None:
    requests = PgMusicRequestRepository(session)
    assert await requests.vote(1, "ауру", "Ауру", _NOW) == 1
    assert await requests.vote(1, "ауру", "АУРУ", _NOW) == 1
    assert await requests.vote(2, "ауру", "ауру", _NOW) == 2
    assert [r.votes for r in await requests.list_open(10)] == [2]
    assert await requests.fulfil(["ауру"], _NOW) == 1
    assert await requests.list_open(10) == []


async def test_chart_counts_distinct_listeners_in_window(session: AsyncSession) -> None:
    tracks = PgTrackRepository(session)
    users, events = PgUserRepository(session), PgUserEventRepository(session)
    hit = await tracks.add(_track("u1", title="Хит"))
    other = await tracks.add(_track("u2", title="Басқа"))
    for user_id in (1, 2, 3):
        await users.upsert(User(telegram_id=user_id))
    for user_id in (1, 2):
        await events.add(user_id, EventKind.TRACK_PLAY, str(hit.id))
    for _ in range(5):
        await events.add(3, EventKind.TRACK_PLAY, str(other.id))
    since, until = _NOW - timedelta(days=3650), _NOW + timedelta(days=3650)
    top = await tracks.top_played(since, until, 10)
    assert [(entry.title, entry.plays) for entry in top] == [("Хит", 2), ("Басқа", 1)]


async def test_chart_log_is_once_per_week(session: AsyncSession) -> None:
    log = PgMusicChartLog(session)
    week = date(2026, 11, 23)
    assert not await log.posted(week)
    await log.record(week, 10, _NOW)
    await log.record(week, 11, _NOW)
    assert await log.posted(week)
