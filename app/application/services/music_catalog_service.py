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
    TrackRepository,
)
from app.application.ports.repositories import UserEventRepository
from app.domain.analytics.events import EventKind
from app.domain.music.collections import COLLECTIONS, Collection, CollectionKind
from app.domain.music.track import AudioUpload, Track, is_music, search_key, track_name

logger = logging.getLogger(__name__)

SHELF_SIZE = 20
REQUESTS_SHOWN = 20
PAGE_MAX = 50
REQUEST_MIN_LEN = 2
REQUEST_MAX_LEN = 128


class IngestOutcome(StrEnum):
    ADDED = "added"          # новый трек в общем каталоге
    EXISTING = "existing"    # такой файл уже есть — просто лёг в коллекцию приславшего
    HIDDEN = "hidden"        # файл убран админом — обратно не принимаем
    NOT_MUSIC = "not_music"  # слишком короткий: звонок, звук, обрывок


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
    ) -> None:
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
        await self._requests.fulfil(
            sorted({
                search_key(track.title),
                search_key(f"{track.performer} {track.title}"),
                search_key(f"{track.title} {track.performer}"),
            }),
            now,
        )
        return IngestResult(IngestOutcome.ADDED, track)

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

    async def get(self, track_id: int) -> Track | None:
        return await self._tracks.get(track_id)

    async def browse(self, popular: bool, limit: int, offset: int) -> list[Track]:
        limit = min(max(limit, 1), PAGE_MAX)
        offset = max(offset, 0)
        if popular:
            return await self._tracks.list_popular(limit, offset)
        return await self._tracks.list_recent(limit, offset)

    async def search(self, query: str, limit: int, offset: int) -> list[Track]:
        text = " ".join(query.split())[:REQUEST_MAX_LEN]
        if not text:
            return []
        return await self._tracks.search(text, min(max(limit, 1), PAGE_MAX), max(offset, 0))

    async def request(self, user_id: int, query: str, now: datetime) -> int | None:
        """Попросить песню, которой нет. None — запрос пустой или слишком длинный."""
        text = " ".join(query.split())
        key = search_key(text)
        if not (REQUEST_MIN_LEN <= len(key) <= REQUEST_MAX_LEN):
            return None
        return await self._requests.vote(user_id, key, text[:REQUEST_MAX_LEN], now)

    async def hide(self, track_id: int) -> bool:
        return await self._tracks.hide(track_id)
