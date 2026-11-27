"""Сервисы музыки на фейках: приём треков, отправка в чат, плейлисты, хит-парад."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime

from app.application.ports.channel import ChannelPost
from app.application.ports.music import MusicRequest, PlaylistAddOutcome
from app.application.ports.telegram import (
    RecipientUnreachableError,
    TelegramTemporarilyUnavailableError,
)
from app.application.services.music_catalog_service import (
    IngestOutcome,
    MusicCatalogService,
    RenameOutcome,
)
from app.application.services.music_chart_service import MusicChartService
from app.application.services.music_delivery_service import (
    ALBUM_SIZE,
    SEND_MAX,
    MusicDeliveryService,
    SendOutcome,
)
from app.application.services.playlist_service import PlaylistService
from app.domain.analytics.events import EventKind
from app.domain.entities.user import User
from app.domain.music.chart import ChartEntry
from app.domain.music.playlist import MAX_PLAYLISTS_PER_USER, Playlist
from app.domain.music.track import AudioUpload, Track, track_key

from tests.fakes import FakeEvents

_NOW = datetime(2026, 11, 27, 19, 0, tzinfo=UTC)


class FakeTracks:
    def __init__(self) -> None:
        self.rows: dict[int, Track] = {}
        self.top: list[ChartEntry] = []

    async def get(self, track_id: int) -> Track | None:
        track = self.rows.get(track_id)
        return track if track and not track.is_hidden else None

    async def by_unique_id(self, file_unique_id: str) -> Track | None:
        return next((t for t in self.rows.values() if t.file_unique_id == file_unique_id), None)

    async def add(self, track: Track) -> Track:
        track.id = len(self.rows) + 1
        self.rows[track.id] = track
        return track

    async def list_by_ids(self, track_ids: Sequence[int]) -> list[Track]:
        return [self.rows[i] for i in track_ids if i in self.rows and not self.rows[i].is_hidden]

    async def find_duplicate(self, key: str, duration_sec: int) -> Track | None:
        return next(
            (t for t in self.rows.values()
             if not t.is_hidden and track_key(t.performer, t.title) == key
             and abs(t.duration_sec - duration_sec) <= 3),
            None,
        )

    async def rename(self, track_id: int, title: str, performer: str) -> None:
        self.rows[track_id].title = title
        self.rows[track_id].performer = performer

    async def list_recent(self, limit: int, offset: int = 0) -> list[Track]:
        return list(self.rows.values())[offset:offset + limit]

    list_popular = list_recent

    async def search(self, key: str, limit: int, offset: int = 0) -> list[Track]:
        return [t for t in self.rows.values() if key in track_key(t.performer, t.title)]

    async def increment_play_count(self, track_id: int) -> None:
        self.rows[track_id].play_count += 1

    async def hide(self, track_id: int) -> bool:
        self.rows[track_id].is_hidden = True
        return True

    async def top_played(self, since: datetime, until: datetime, limit: int) -> list[ChartEntry]:
        return self.top[:limit]

    async def top_tracks(self, since: datetime, until: datetime, limit: int) -> list[Track]:
        return []

    async def count_added(self, since: datetime, until: datetime) -> int:
        return len(self.rows)


class FakeLibrary:
    def __init__(self) -> None:
        self.saved: set[tuple[int, int]] = set()

    async def add(self, user_id: int, track_id: int, at: datetime) -> bool:
        added = (user_id, track_id) not in self.saved
        self.saved.add((user_id, track_id))
        return added

    async def remove(self, user_id: int, track_id: int) -> bool:
        removed = (user_id, track_id) in self.saved
        self.saved.discard((user_id, track_id))
        return removed

    async def list_for_user(self, user_id: int, limit: int, offset: int = 0) -> list[Track]:
        return []

    async def list_ids(self, user_id: int) -> list[int]:
        return [t for u, t in self.saved if u == user_id]


class FakeRequests:
    def __init__(self) -> None:
        self.fulfilled: list[str] = []
        self.open: list[MusicRequest] = []

    async def vote(self, user_id: int, key: str, query: str, at: datetime) -> int:
        return 1

    async def list_open(self, limit: int) -> list[MusicRequest]:
        return self.open[:limit]

    async def fulfil(self, keys: Sequence[str], at: datetime) -> int:
        self.fulfilled.extend(keys)
        return len(keys)


class FakeArchive:
    def __init__(self, message_id: int | None = 900) -> None:
        self.message_id = message_id
        self.stored: list[str] = []

    async def store(self, file_id: str, caption: str) -> int | None:
        self.stored.append(file_id)
        return self.message_id


def _catalog() -> tuple[MusicCatalogService, FakeTracks, FakeLibrary, FakeRequests, FakeEvents]:
    tracks, library, requests, events = FakeTracks(), FakeLibrary(), FakeRequests(), FakeEvents()
    service = MusicCatalogService(tracks, library, requests, FakeArchive(), events)
    return service, tracks, library, requests, events


def _upload(unique: str = "u1", duration: int = 200) -> AudioUpload:
    return AudioUpload(
        file_id=f"file-{unique}", file_unique_id=unique, duration_sec=duration,
        title="Ауру", performer="Қайрат Нұртас",
    )


async def test_first_upload_lands_in_catalog_archive_and_uploader_library() -> None:
    service, _tracks, library, requests, events = _catalog()
    result = await service.ingest(_upload(), 42, _NOW)
    assert result.outcome is IngestOutcome.ADDED and result.track is not None
    assert result.track.archive_message_id == 900
    assert (42, result.track.id) in library.saved
    assert (42, EventKind.TRACK_UPLOAD, str(result.track.id)) in events.added
    # Песню, которую просили «исполнитель название», закрываем.
    assert "kairat nurtas auru" in requests.fulfilled


async def test_same_file_from_another_listener_is_not_duplicated() -> None:
    service, tracks, library, _, _ = _catalog()
    first = await service.ingest(_upload(), 42, _NOW)
    second = await service.ingest(_upload(), 7, _NOW)
    assert second.outcome is IngestOutcome.EXISTING
    assert len(tracks.rows) == 1
    assert first.track is not None and (7, first.track.id) in library.saved


async def test_hidden_track_does_not_come_back_by_forwarding() -> None:
    service, _tracks, _, _, _ = _catalog()
    first = await service.ingest(_upload(), 42, _NOW)
    assert first.track is not None and first.track.id is not None
    await service.hide(first.track.id)
    again = await service.ingest(_upload(), 7, _NOW)
    assert again.outcome is IngestOutcome.HIDDEN


async def test_ringtone_length_audio_is_rejected() -> None:
    service, tracks, _, _, _ = _catalog()
    result = await service.ingest(_upload(duration=3), 42, _NOW)
    assert result.outcome is IngestOutcome.NOT_MUSIC and not tracks.rows


async def test_empty_request_is_refused() -> None:
    service, *_ = _catalog()
    assert await service.request(1, "  ! ", _NOW) is None
    assert await service.request(1, "Ауру", _NOW) == 1


# ── отправка в чат ─────────────────────────────────────────────────────────────


class FakeSender:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.singles: list[str] = []
        self.albums: list[list[str]] = []

    async def send_audio(self, chat_id: int, file_id: str, caption: str) -> int:
        if self.error:
            raise self.error
        self.singles.append(file_id)
        return 1

    async def send_audio_album(self, chat_id: int, file_ids: Sequence[str], caption: str) -> int:
        if self.error:
            raise self.error
        self.albums.append(list(file_ids))
        return len(file_ids)


class FakeUsers:
    def __init__(self) -> None:
        self.bot_started: dict[int, datetime | None] = {}

    async def set_bot_started(self, telegram_id: int, at: datetime | None) -> None:
        self.bot_started[telegram_id] = at


class FakeLock:
    def __init__(self, free: bool = True) -> None:
        self.free = free

    async def acquire(self, key: str, ttl_seconds: int) -> bool:
        return self.free


async def _delivery(
    sender: FakeSender, count: int = 1, lock: FakeLock | None = None
) -> tuple[MusicDeliveryService, FakeTracks, FakeUsers, FakeEvents]:
    tracks, users, events = FakeTracks(), FakeUsers(), FakeEvents()
    for index in range(count):
        await tracks.add(Track(
            title=f"t{index}", performer="p", duration_sec=100,
            telegram_file_id=f"f{index}", file_unique_id=f"u{index}", uploader_id=1,
        ))
    service = MusicDeliveryService(
        tracks, sender, users, events, lock or FakeLock(), "qazaqcinema_bot"  # type: ignore[arg-type]
    )
    return service, tracks, users, events


async def test_single_track_goes_to_chat_and_counts_as_play() -> None:
    sender = FakeSender()
    service, tracks, users, events = await _delivery(sender)
    outcome = await service.send_track(User(telegram_id=5), 1, _NOW)
    assert outcome is SendOutcome.SENT
    assert sender.singles == ["f0"]
    assert tracks.rows[1].play_count == 1
    assert users.bot_started[5] == _NOW
    assert (5, EventKind.TRACK_PLAY, "1") in events.added


async def test_playlist_goes_as_albums_of_ten_and_is_capped() -> None:
    sender = FakeSender()
    service, _, _, _ = await _delivery(sender, count=SEND_MAX + 7)
    outcome = await service.send_tracks(User(telegram_id=5), list(range(1, SEND_MAX + 8)), _NOW)
    assert outcome is SendOutcome.SENT
    assert sum(len(album) for album in sender.albums) == SEND_MAX
    assert all(len(album) <= ALBUM_SIZE for album in sender.albums)


async def test_closed_chat_clears_bot_flag_so_front_asks_to_open_bot() -> None:
    service, _, users, _ = await _delivery(FakeSender(RecipientUnreachableError("x")))
    user = User(telegram_id=5, bot_started_at=_NOW)
    assert await service.send_track(user, 1, _NOW) is SendOutcome.BOT_BLOCKED
    assert users.bot_started[5] is None


async def test_flood_limit_is_try_later_and_keeps_flag() -> None:
    service, _, users, _ = await _delivery(FakeSender(TelegramTemporarilyUnavailableError("x")))
    assert await service.send_track(User(telegram_id=5), 1, _NOW) is SendOutcome.TRY_LATER
    assert 5 not in users.bot_started


async def test_double_tap_does_not_send_twice() -> None:
    sender = FakeSender()
    service, _, _, _ = await _delivery(sender, lock=FakeLock(free=False))
    assert await service.send_track(User(telegram_id=5), 1, _NOW) is SendOutcome.BUSY
    assert not sender.singles


async def test_unknown_track_is_not_found() -> None:
    service, _, _, _ = await _delivery(FakeSender())
    assert await service.send_track(User(telegram_id=5), 99, _NOW) is SendOutcome.NOT_FOUND


# ── плейлисты ──────────────────────────────────────────────────────────────────


class FakePlaylists:
    def __init__(self) -> None:
        self.rows: dict[int, Playlist] = {}
        self.items: dict[int, list[int]] = {}

    async def create(self, playlist: Playlist) -> Playlist:
        playlist.id = len(self.rows) + 1
        self.rows[playlist.id] = playlist
        self.items[playlist.id] = []
        return playlist

    async def get(self, playlist_id: int) -> Playlist | None:
        return self.rows.get(playlist_id)

    async def by_share_code(self, share_code: str) -> Playlist | None:
        return next((p for p in self.rows.values() if p.share_code == share_code), None)

    async def list_for_owner(self, owner_id: int) -> list[Playlist]:
        return [p for p in self.rows.values() if p.owner_id == owner_id]

    async def count_for_owner(self, owner_id: int) -> int:
        return len(await self.list_for_owner(owner_id))

    async def rename(self, playlist_id: int, title: str, at: datetime) -> None:
        self.rows[playlist_id].title = title

    async def set_public(self, playlist_id: int, is_public: bool, at: datetime) -> None:
        self.rows[playlist_id].is_public = is_public

    async def list_public(self, limit: int) -> list[Playlist]:
        return [p for p in self.rows.values() if p.is_public][:limit]

    async def increment_saves(self, playlist_id: int) -> None:
        self.rows[playlist_id].saves_count += 1

    async def delete(self, playlist_id: int) -> None:
        del self.rows[playlist_id]

    async def add_track(
        self, playlist_id: int, track_id: int, at: datetime, limit: int
    ) -> PlaylistAddOutcome:
        if track_id in self.items[playlist_id]:
            return PlaylistAddOutcome.DUPLICATE
        self.items[playlist_id].append(track_id)
        return PlaylistAddOutcome.ADDED

    async def add_tracks(
        self, playlist_id: int, track_ids: Sequence[int], at: datetime, limit: int
    ) -> int:
        self.items[playlist_id].extend(track_ids)
        return len(track_ids)

    async def remove_track(self, playlist_id: int, track_id: int, at: datetime) -> bool:
        self.items[playlist_id].remove(track_id)
        return True

    async def track_ids(self, playlist_id: int) -> list[int]:
        return list(self.items[playlist_id])

    async def reorder(self, playlist_id: int, track_ids: Sequence[int], at: datetime) -> bool:
        if sorted(track_ids) != sorted(self.items[playlist_id]):
            return False
        self.items[playlist_id] = list(track_ids)
        return True


async def _playlists() -> tuple[PlaylistService, FakePlaylists, FakeTracks]:
    playlists, tracks = FakePlaylists(), FakeTracks()
    await tracks.add(Track(
        title="t", performer="p", duration_sec=100, telegram_file_id="f",
        file_unique_id="u", uploader_id=1,
    ))
    return PlaylistService(playlists, tracks), playlists, tracks


async def test_only_owner_can_change_a_playlist() -> None:
    service, _, _ = await _playlists()
    mine = await service.create(1, "Жол", _NOW)
    assert mine is not None and mine.id is not None
    assert await service.add_track(2, mine.id, 1, _NOW) is None
    assert not await service.rename(2, mine.id, "x", _NOW)
    assert not await service.delete(2, mine.id)
    assert await service.open(2, mine.id) is None
    assert await service.add_track(1, mine.id, 1, _NOW) is PlaylistAddOutcome.ADDED


async def test_unknown_track_is_not_added() -> None:
    service, _, _ = await _playlists()
    mine = await service.create(1, None, _NOW)
    assert mine is not None and mine.id is not None
    assert await service.add_track(1, mine.id, 404, _NOW) is None


async def test_playlist_limit_per_listener() -> None:
    service, _, _ = await _playlists()
    for _ in range(MAX_PLAYLISTS_PER_USER):
        assert await service.create(1, "x", _NOW) is not None
    assert await service.create(1, "x", _NOW) is None


async def test_shared_playlist_is_saved_as_independent_copy() -> None:
    service, playlists, _ = await _playlists()
    source = await service.create(1, "Той", _NOW)
    assert source is not None and source.id is not None
    await service.add_track(1, source.id, 1, _NOW)
    copy = await service.save_shared(2, source.share_code, _NOW)
    assert copy is not None and copy.id is not None and copy.id != source.id
    assert copy.owner_id == 2 and copy.title == "Той"
    assert playlists.items[copy.id] == [1]
    await service.delete(1, source.id)
    assert playlists.items[copy.id] == [1]


async def test_saving_own_shared_link_does_not_duplicate() -> None:
    service, playlists, _ = await _playlists()
    source = await service.create(1, "Той", _NOW)
    assert source is not None
    again = await service.save_shared(1, source.share_code, _NOW)
    assert again is source and len(playlists.rows) == 1


# ── хит-парад ──────────────────────────────────────────────────────────────────


class FakeChartLog:
    def __init__(self) -> None:
        self.weeks: dict[date, int] = {}

    async def posted(self, week: date) -> bool:
        return week in self.weeks

    async def record(self, week: date, message_id: int, at: datetime) -> None:
        self.weeks[week] = message_id


class FakePublisher:
    def __init__(self) -> None:
        self.posts: list[ChannelPost] = []

    async def publish(self, post: ChannelPost) -> int | None:
        self.posts.append(post)
        return 77


async def test_weekly_chart_is_posted_once_per_week_with_music_button() -> None:
    tracks, publisher = FakeTracks(), FakePublisher()
    tracks.top = [ChartEntry("Ауру", "Қайрат Нұртас", 30)]
    service = MusicChartService(
        tracks, FakeRequests(), FakeChartLog(), publisher, "qazaqcinema_bot"  # type: ignore[arg-type]
    )
    assert await service.publish_weekly(_NOW)
    assert not await service.publish_weekly(_NOW)
    assert len(publisher.posts) == 1
    assert publisher.posts[0].button_url == "https://t.me/qazaqcinema_bot?startapp=music"


async def test_week_without_listens_posts_nothing() -> None:
    publisher = FakePublisher()
    service = MusicChartService(
        FakeTracks(), FakeRequests(), FakeChartLog(), publisher, "bot"  # type: ignore[arg-type]
    )
    assert not await service.publish_weekly(_NOW)
    assert not publisher.posts


async def test_only_owner_reorders_and_order_is_kept() -> None:
    service, _, tracks = await _playlists()
    await tracks.add(Track(
        title="t2", performer="p", duration_sec=100, telegram_file_id="f2",
        file_unique_id="u2", uploader_id=1,
    ))
    mine = await service.create(1, "Ретпен", _NOW)
    assert mine is not None and mine.id is not None
    await service.add_track(1, mine.id, 1, _NOW)
    await service.add_track(1, mine.id, 2, _NOW)
    assert not await service.reorder(2, mine.id, [2, 1], _NOW)
    assert await service.reorder(1, mine.id, [2, 1], _NOW)
    view = await service.open(1, mine.id)
    assert view is not None and [t.id for t in view.tracks] == [2, 1]


async def test_send_keeps_the_order_it_was_given() -> None:
    sender = FakeSender()
    service, _, _, _ = await _delivery(sender, count=3)
    assert await service.send_tracks(User(telegram_id=5), [3, 1, 2], _NOW) is SendOutcome.SENT
    assert sender.albums == [["f2", "f0", "f1"]]


async def test_shared_copy_counts_a_save_and_public_switch_is_owner_only() -> None:
    service, playlists, _ = await _playlists()
    source = await service.create(1, "Той", _NOW)
    assert source is not None and source.id is not None
    assert not await service.set_public(2, source.id, True, _NOW)
    assert await service.set_public(1, source.id, True, _NOW)
    assert [p.id for p in await service.list_public(10)] == [source.id]
    await service.save_shared(2, source.share_code, _NOW)
    assert playlists.rows[source.id].saves_count == 1


async def test_playlist_created_with_tracks_keeps_only_known_ones() -> None:
    service, playlists, _ = await _playlists()
    created = await service.create(1, "Үздіктер", _NOW, [1, 404])
    assert created is not None and created.id is not None
    assert playlists.items[created.id] == [1]


async def test_empty_collections_are_hidden() -> None:
    service, *_ = _catalog()
    assert await service.collections(_NOW) == []
    await service.ingest(_upload(), 42, _NOW)
    keys = [view.collection.kind.value for view in await service.collections(_NOW)]
    # Хитов недели ещё нет (никто не слушал), новые и лучшие уже есть.
    assert keys == ["new", "best"]


async def test_same_song_from_another_file_is_not_a_second_track() -> None:
    service, tracks, library, _, _ = _catalog()
    first = await service.ingest(_upload("u1", 200), 42, _NOW)
    # Другой файл (другой канал, битрейт), те же теги, длительность на секунду иная.
    again = await service.ingest(_upload("u2", 201), 7, _NOW)
    assert again.outcome is IngestOutcome.EXISTING
    assert len(tracks.rows) == 1
    assert first.track is not None and (7, first.track.id) in library.saved
    # Другая длительность — уже другая запись (ремикс, live).
    other = await service.ingest(_upload("u3", 260), 7, _NOW)
    assert other.outcome is IngestOutcome.ADDED


async def test_search_ignores_kazakh_letters_latin_and_word_order() -> None:
    service, *_ = _catalog()
    await service.ingest(_upload(), 42, _NOW)
    for query in ("Кайрат Нуртас", "kairat", "Qairat Nurtas", "ауру"):
        assert [t.title for t in await service.search(query, 10, 0)] == ["Ауру"], query
    assert await service.search("  !! ", 10, 0) == []


async def test_only_uploader_or_admin_renames_and_format_is_checked() -> None:
    service, tracks, *_ = _catalog()
    added = await service.ingest(_upload(), 42, _NOW)
    assert added.track is not None and added.track.id is not None
    track_id = added.track.id
    assert await service.rename(track_id, 7, False, "А — Б") is RenameOutcome.FORBIDDEN
    assert await service.rename(track_id, 42, False, "Ауру") is RenameOutcome.BAD_FORMAT
    assert await service.rename(404, 42, False, "А — Б") is RenameOutcome.NOT_FOUND
    assert await service.rename(track_id, 42, False, "Ninety One — Сен") is RenameOutcome.RENAMED
    assert (tracks.rows[track_id].performer, tracks.rows[track_id].title) == ("Ninety One", "Сен")
    assert await service.rename(track_id, 1, True, "Dimash — Sinful") is RenameOutcome.RENAMED
