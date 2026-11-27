"""Интеграционные тесты музыки (Postgres): дубли, счётчики, плейлисты, запросы, хит-парад."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.application.ports.music import PlaylistAddOutcome
from app.domain.analytics.events import EventKind
from app.domain.entities.user import User
from app.domain.music.playlist import Playlist
from app.domain.music.search import fold
from app.domain.music.track import Track, track_key
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
    )


async def test_same_file_twice_is_one_row(session: AsyncSession) -> None:
    tracks = PgTrackRepository(session)
    first = await tracks.add(_track("u1"))
    second = await tracks.add(_track("u1", title="Другое"))
    assert first.id == second.id and second.title == "Ауру"


async def test_search_by_folded_key_any_order_and_typos(session: AsyncSession) -> None:
    tracks = PgTrackRepository(session)
    await tracks.add(_track("u1"))
    await tracks.add(_track("u2", title="Сен", performer="Ninety One"))

    async def titles(query: str) -> list[str]:
        return [t.title for t in await tracks.search(fold(query), 10)]

    assert await titles("Нұртас ауру") == ["Ауру"]
    assert await titles("ауру кайрат") == ["Ауру"]          # другой порядок слов
    assert await titles("Qairat Nurtas") == ["Ауру"]        # латиница
    assert await titles("каират нуртсас") == ["Ауру"]       # опечатки
    assert await titles("ninety") == ["Сен"]


async def test_duplicate_is_found_by_key_and_close_duration(session: AsyncSession) -> None:
    tracks = PgTrackRepository(session)
    track = await tracks.add(_track("u1"))
    assert track.id is not None
    key = track_key("Кайрат Нуртас", "АУРУ")
    assert (await tracks.find_duplicate(key, 202)) is not None
    assert await tracks.find_duplicate(key, 230) is None
    await tracks.rename(track.id, "Сен", "Ninety One")
    assert await tracks.find_duplicate(key, 200) is None
    assert [t.id for t in await tracks.search(fold("ninety sen"), 10)] == [track.id]


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


async def test_reorder_sets_play_order_and_rejects_stale_set(session: AsyncSession) -> None:
    tracks, playlists = PgTrackRepository(session), PgPlaylistRepository(session)
    ids = [(await tracks.add(_track(f"r{i}"))).id for i in range(3)]
    assert all(track_id is not None for track_id in ids)
    track_ids = [track_id for track_id in ids if track_id is not None]
    playlist = await playlists.create(
        Playlist(owner_id=5, title="Ретпен", share_code="ord12345", created_at=_NOW)
    )
    assert playlist.id is not None
    await playlists.add_tracks(playlist.id, track_ids, _NOW, 10)
    reversed_ids = list(reversed(track_ids))
    assert await playlists.reorder(playlist.id, reversed_ids, _NOW)
    assert await playlists.track_ids(playlist.id) == reversed_ids
    # Экран устарел (трек удалили) — порядок не принимается, ничего не теряется.
    assert not await playlists.reorder(playlist.id, reversed_ids[:2], _NOW)
    assert not await playlists.reorder(playlist.id, [*reversed_ids[:2], reversed_ids[0]], _NOW)
    assert await playlists.track_ids(playlist.id) == reversed_ids


async def test_public_playlists_are_non_empty_and_most_saved_first(session: AsyncSession) -> None:
    tracks, playlists = PgTrackRepository(session), PgPlaylistRepository(session)
    track = await tracks.add(_track("p1"))
    assert track.id is not None
    made = []
    for index, code in enumerate(("pub11111", "pub22222", "pub33333")):
        playlist = await playlists.create(
            Playlist(owner_id=index, title=code, share_code=code, created_at=_NOW)
        )
        assert playlist.id is not None
        made.append(playlist.id)
    first, second, empty = made
    for playlist_id in made:
        await playlists.set_public(playlist_id, True, _NOW)
    await playlists.add_tracks(first, [track.id], _NOW, 10)
    await playlists.add_tracks(second, [track.id], _NOW, 10)
    await playlists.increment_saves(second)
    assert [p.id for p in await playlists.list_public(10)] == [second, first]
    await playlists.set_public(second, False, _NOW)
    assert [p.id for p in await playlists.list_public(10)] == [first]
    assert empty not in [p.id for p in await playlists.list_public(10)]


async def test_week_hits_are_tracks_with_most_distinct_listeners(session: AsyncSession) -> None:
    tracks = PgTrackRepository(session)
    users, events = PgUserRepository(session), PgUserEventRepository(session)
    hit = await tracks.add(_track("h1", title="Хит"))
    other = await tracks.add(_track("h2", title="Басқа"))
    for user_id in (1, 2):
        await users.upsert(User(telegram_id=user_id))
        await events.add(user_id, EventKind.TRACK_PLAY, str(hit.id))
    await events.add(1, EventKind.TRACK_PLAY, str(other.id))
    since, until = _NOW - timedelta(days=3650), _NOW + timedelta(days=3650)
    assert [t.title for t in await tracks.top_tracks(since, until, 10)] == ["Хит", "Басқа"]
