"""Общий каталог музыки: приём треков от слушателей, витрина, поиск, запросы.

Каталог растёт сам: любой, кто прислал или переслал боту аудио, добавляет его для
всех. Модерации до публикации нет — по решению продукта; жалобу или требование
правообладателя админ закрывает `/trackhide <id>`, и скрытый трек не возвращается
повторной пересылкой.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.application.ports.music import (
    LibraryRepository,
    MusicArchive,
    MusicRequest,
    MusicRequestRepository,
    PlaylistRepository,
    RequestNotifier,
    TrackRepository,
    TrackStats,
)
from app.application.ports.repositories import UserEventRepository
from app.domain.analytics.events import EventKind
from app.domain.music.collections import COLLECTIONS, Collection, CollectionKind
from app.domain.music.playlist import Playlist
from app.domain.music.search import fold
from app.domain.music.track import (
    AudioUpload,
    Track,
    is_music,
    parse_name,
    search_key,
    track_key,
    track_name,
)

logger = logging.getLogger(__name__)

SHELF_SIZE = 20
REQUESTS_SHOWN = 20
PAGE_MAX = 50
REQUEST_MIN_LEN = 2
# Потолок писем «сіз сұраған ән қосылды» на один трек: приём идёт в обработчике
# сообщения, и сотня отправок подряд задержала бы ответ загрузившему.
NOTIFY_MAX = 50
REQUEST_MAX_LEN = 128


class IngestOutcome(StrEnum):
    ADDED = "added"          # новый трек в общем каталоге
    EXISTING = "existing"    # такой файл уже есть — просто лёг в коллекцию приславшего
    HIDDEN = "hidden"        # файл убран админом — обратно не принимаем
    NOT_MUSIC = "not_music"  # слишком короткий: звонок, звук, обрывок


class RenameOutcome(StrEnum):
    RENAMED = "renamed"
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"    # не загружал этот трек и не админ
    BAD_FORMAT = "bad_format"  # нет «Орындаушы — Атауы»


@dataclass(frozen=True, slots=True)
class IngestResult:
    outcome: IngestOutcome
    track: Track | None = None


@dataclass(frozen=True, slots=True)
class CollectionView:
    collection: Collection
    tracks: list[Track]


# Окно «хитов недели» — скользящие 7 суток: подборка не пустеет в понедельник утром.
_HITS_WINDOW = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class TrackDetails:
    track: Track
    stats: TrackStats
    by_artist: list[Track]
    similar: list[Track]
    playlists: list[Playlist]


@dataclass(frozen=True, slots=True)
class ArtistPage:
    name: str
    tracks: list[Track]


# Сколько показывать на странице трека в каждом блоке.
DETAIL_SHELF = 10
ARTIST_PAGE_MAX = 200


@dataclass(frozen=True, slots=True)
class MusicHome:
    recent: list[Track]
    popular: list[Track]
    requests: list[MusicRequest]


class MusicCatalogService:
    def __init__(
        self,
        tracks: TrackRepository,
        library: LibraryRepository,
        requests: MusicRequestRepository,
        archive: MusicArchive,
        events: UserEventRepository,
        playlists: PlaylistRepository,
        notifier: RequestNotifier,
    ) -> None:
        self._playlists = playlists
        self._notifier = notifier
        self._tracks = tracks
        self._library = library
        self._requests = requests
        self._archive = archive
        self._events = events

    async def ingest(self, upload: AudioUpload, uploader_id: int, now: datetime) -> IngestResult:
        if not is_music(upload):
            return IngestResult(IngestOutcome.NOT_MUSIC)
        existing = await self._tracks.by_unique_id(upload.file_unique_id)
        if existing is not None:
            if existing.is_hidden or existing.id is None:
                return IngestResult(IngestOutcome.HIDDEN)
            await self._library.add(uploader_id, existing.id, now)
            return IngestResult(IngestOutcome.EXISTING, existing)

        name = track_name(upload)
        # Та же песня другим файлом (другой канал, другой битрейт) — не плодим дубль в
        # поиске: человек получает уже существующий трек к себе.
        duplicate = await self._tracks.find_duplicate(
            track_key(name.performer, name.title), upload.duration_sec
        )
        if duplicate is not None and duplicate.id is not None:
            await self._library.add(uploader_id, duplicate.id, now)
            return IngestResult(IngestOutcome.EXISTING, duplicate)
        archive_id = await self._archive.store(
            upload.file_id, f"{name.performer} — {name.title}\n#u{uploader_id}"
        )
        track = await self._tracks.add(Track(
            title=name.title,
            performer=name.performer,
            duration_sec=upload.duration_sec,
            telegram_file_id=upload.file_id,
            file_unique_id=upload.file_unique_id,
            uploader_id=uploader_id,
            file_size=upload.file_size,
            mime_type=upload.mime_type,
            archive_message_id=archive_id,
        ))
        if track.id is None:
            return IngestResult(IngestOutcome.HIDDEN)
        await self._library.add(uploader_id, track.id, now)
        await self._events.add(uploader_id, EventKind.TRACK_UPLOAD, str(track.id))
        # Песню, которую просили, закрываем — запрос сравнивается целиком в любом порядке
        # «исполнитель название», как его обычно и набирают.
        voters = await self._requests.fulfil(
            sorted({
                search_key(track.title),
                search_key(f"{track.performer} {track.title}"),
                search_key(f"{track.title} {track.performer}"),
            }),
            now,
        )
        # Ждавшим песню — личное письмо: человек возвращается сам, а загрузивший помог
        # кому-то конкретному. Себе не пишем: он и так знает, что прислал.
        for voter in [v for v in voters if v != uploader_id][:NOTIFY_MAX]:
            await self._notifier.request_fulfilled(voter, track)
        return IngestResult(IngestOutcome.ADDED, track)

    async def uploaded_by(self, user_id: int) -> int:
        return await self._tracks.count_uploaded(user_id)

    async def home(self) -> MusicHome:
        return MusicHome(
            recent=await self._tracks.list_recent(SHELF_SIZE),
            popular=await self._tracks.list_popular(SHELF_SIZE),
            requests=await self._requests.list_open(REQUESTS_SHOWN),
        )

    async def collection(self, collection: Collection, now: datetime) -> CollectionView:
        if collection.kind is CollectionKind.WEEK_HITS:
            tracks = await self._tracks.top_tracks(now - _HITS_WINDOW, now, collection.size)
        elif collection.kind is CollectionKind.NEW:
            tracks = await self._tracks.list_recent(collection.size)
        else:
            tracks = await self._tracks.list_popular(collection.size)
        return CollectionView(collection, tracks)

    async def collections(self, now: datetime) -> list[CollectionView]:
        """Все готовые подборки; пустые не показываем — «плейлист из нуля песен» как поломка."""
        views = [await self.collection(c, now) for c in COLLECTIONS]
        return [view for view in views if view.tracks]

    async def details(self, track_id: int) -> TrackDetails | None:
        """Страница трека: цифры, другие песни исполнителя, похожие и плейлисты с ним.

        «Ұқсас» добирается популярными, если совместных плейлистов ещё мало: пустой
        блок на новом треке выглядел бы как поломка, а популярное — честная подсказка.
        """
        track = await self._tracks.get(track_id)
        if track is None or track.id is None:
            return None
        artist = [
            t for t in await self._tracks.by_performer(fold(track.performer), DETAIL_SHELF + 1)
            if t.id != track.id
        ][:DETAIL_SHELF]
        seen = {track.id, *(t.id for t in artist)}
        co_listened = await self._tracks.co_listened(track.id, DETAIL_SHELF)
        similar = [t for t in co_listened if t.id not in seen]
        if len(similar) < DETAIL_SHELF:
            seen.update(t.id for t in similar)
            similar += [
                t for t in await self._tracks.list_popular(DETAIL_SHELF * 2) if t.id not in seen
            ][: DETAIL_SHELF - len(similar)]
        return TrackDetails(
            track=track,
            stats=await self._tracks.stats(track.id),
            by_artist=artist,
            similar=similar,
            playlists=await self._playlists.public_with_track(track.id, DETAIL_SHELF),
        )

    async def artist(self, performer_key: str) -> ArtistPage | None:
        tracks = await self._tracks.by_performer(performer_key, ARTIST_PAGE_MAX)
        if not tracks:
            return None
        return ArtistPage(tracks[0].performer, tracks)

    async def performers(self, limit: int) -> list[tuple[str, int]]:
        return await self._tracks.performers(limit)

    async def all_tracks(self) -> list[Track]:
        """Весь видимый каталог — только для sitemap."""
        return await self._tracks.list_all()

    async def get(self, track_id: int) -> Track | None:
        return await self._tracks.get(track_id)

    async def browse(self, popular: bool, limit: int, offset: int) -> list[Track]:
        limit = min(max(limit, 1), PAGE_MAX)
        offset = max(offset, 0)
        if popular:
            return await self._tracks.list_popular(limit, offset)
        return await self._tracks.list_recent(limit, offset)

    async def search(self, query: str, limit: int, offset: int) -> list[Track]:
        """«каират нуртас», «Qairat», «ауру кайрат» — всё сводится к одному ключу."""
        key = fold(query[:REQUEST_MAX_LEN])
        if not key:
            return []
        return await self._tracks.search(key, min(max(limit, 1), PAGE_MAX), max(offset, 0))

    async def rename(
        self, track_id: int, user_id: int, is_admin: bool, raw: str
    ) -> RenameOutcome:
        """Исправить «Орындаушы — Атауы»: может тот, кто прислал трек, и админ."""
        track = await self._tracks.get(track_id)
        if track is None or track.id is None:
            return RenameOutcome.NOT_FOUND
        if track.uploader_id != user_id and not is_admin:
            return RenameOutcome.FORBIDDEN
        name = parse_name(raw)
        if name is None:
            return RenameOutcome.BAD_FORMAT
        await self._tracks.rename(track.id, name.title, name.performer)
        return RenameOutcome.RENAMED

    async def request(self, user_id: int, query: str, now: datetime) -> int | None:
        """Попросить песню, которой нет. None — запрос пустой или слишком длинный."""
        text = " ".join(query.split())
        key = search_key(text)
        if not (REQUEST_MIN_LEN <= len(key) <= REQUEST_MAX_LEN):
            return None
        return await self._requests.vote(user_id, key, text[:REQUEST_MAX_LEN], now)

    async def hide(self, track_id: int) -> bool:
        return await self._tracks.hide(track_id)
