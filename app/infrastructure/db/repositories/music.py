"""Pg-адаптеры музыки: каталог треков, коллекция, плейлисты, запросы, хит-парад."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import ColumnElement, Integer, and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.music import MusicRequest, PlaylistAddOutcome, TrackStats
from app.domain.analytics.events import EventKind
from app.domain.music.chart import ChartEntry
from app.domain.music.playlist import Playlist
from app.domain.music.search import fold, words
from app.domain.music.track import DUPLICATE_SECONDS, Track, track_key
from app.infrastructure.db.models import UserEventModel
from app.infrastructure.db.music_models import (
    MusicChartPostModel,
    MusicRequestModel,
    MusicRequestVoteModel,
    PlaylistModel,
    PlaylistTrackModel,
    TrackModel,
    UserTrackModel,
)
from app.infrastructure.db.sql import rowcount


def _track_to_domain(model: TrackModel) -> Track:
    return Track(
        id=model.id,
        title=model.title,
        performer=model.performer,
        duration_sec=model.duration_sec,
        telegram_file_id=model.telegram_file_id,
        file_unique_id=model.file_unique_id,
        uploader_id=model.uploader_id,
        file_size=model.file_size,
        mime_type=model.mime_type,
        archive_message_id=model.archive_message_id,
        play_count=model.play_count,
        saves_count=model.saves_count,
        is_hidden=model.is_hidden,
        created_at=model.created_at,
    )


_visible = TrackModel.is_hidden.is_(False)


class PgTrackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, track_id: int) -> Track | None:
        model = await self._session.scalar(
            select(TrackModel).where(TrackModel.id == track_id, _visible)
        )
        return _track_to_domain(model) if model else None

    async def by_unique_id(self, file_unique_id: str) -> Track | None:
        model = await self._session.scalar(
            select(TrackModel).where(TrackModel.file_unique_id == file_unique_id)
        )
        return _track_to_domain(model) if model else None

    async def add(self, track: Track) -> Track:
        values = {
            "title": track.title,
            "performer": track.performer,
            "search_key": track_key(track.performer, track.title),
            "duration_sec": track.duration_sec,
            "telegram_file_id": track.telegram_file_id,
            "file_unique_id": track.file_unique_id,
            "file_size": track.file_size,
            "mime_type": track.mime_type,
            "archive_message_id": track.archive_message_id,
            "uploader_id": track.uploader_id,
        }
        stmt = (
            pg_insert(TrackModel)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["file_unique_id"])
            .returning(TrackModel.id)
        )
        inserted = await self._session.scalar(stmt)
        await self._session.commit()
        if inserted is None:
            existing = await self.by_unique_id(track.file_unique_id)
            assert existing is not None  # конфликт по UNIQUE значит, что строка есть
            return existing
        stored = await self._session.get(TrackModel, inserted)
        assert stored is not None
        return _track_to_domain(stored)

    async def list_by_ids(self, track_ids: Sequence[int]) -> list[Track]:
        if not track_ids:
            return []
        result = await self._session.scalars(
            select(TrackModel).where(TrackModel.id.in_(track_ids), _visible)
        )
        found = {model.id: _track_to_domain(model) for model in result}
        return [found[track_id] for track_id in track_ids if track_id in found]

    async def list_recent(self, limit: int, offset: int = 0) -> list[Track]:
        stmt = (
            select(TrackModel).where(_visible)
            .order_by(TrackModel.id.desc()).limit(limit).offset(offset)
        )
        return [_track_to_domain(model) for model in await self._session.scalars(stmt)]

    async def list_popular(self, limit: int, offset: int = 0) -> list[Track]:
        # Сохранение в коллекцию весит больше прослушивания: послушать могут случайно,
        # забрать себе — только то, что понравилось.
        score = TrackModel.play_count + TrackModel.saves_count * 3
        stmt = (
            select(TrackModel).where(_visible)
            .order_by(score.desc(), TrackModel.id.desc()).limit(limit).offset(offset)
        )
        return [_track_to_domain(model) for model in await self._session.scalars(stmt)]

    # Порог нечёткого совпадения: ниже — уже другие песни, а не опечатка.
    _FUZZY_THRESHOLD = 0.45

    async def search(self, key: str, limit: int, offset: int = 0) -> list[Track]:
        """Все слова запроса в ключе (любой порядок) → выше; иначе нечёткое сходство.

        `word_similarity` сравнивает запрос с самым похожим куском ключа, поэтому
        «каират нуртас» находит «Қайрат Нұртас — Ауру» даже с опечаткой и без названия.
        """
        terms = words(key) or [key]
        all_words = and_(*(TrackModel.search_key.contains(term) for term in terms))
        fuzzy = func.word_similarity(key, TrackModel.search_key)
        stmt = (
            select(TrackModel)
            .where(_visible, or_(all_words, fuzzy > self._FUZZY_THRESHOLD))
            .order_by(
                all_words.desc(),
                fuzzy.desc(),
                (TrackModel.play_count + TrackModel.saves_count * 3).desc(),
                TrackModel.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return [_track_to_domain(model) for model in await self._session.scalars(stmt)]

    async def find_duplicate(self, key: str, duration_sec: int) -> Track | None:
        model = await self._session.scalar(
            select(TrackModel)
            .where(
                _visible,
                TrackModel.search_key == key,
                func.abs(TrackModel.duration_sec - duration_sec) <= DUPLICATE_SECONDS,
            )
            .order_by(TrackModel.id)
            .limit(1)
        )
        return _track_to_domain(model) if model else None

    async def rename(self, track_id: int, title: str, performer: str) -> None:
        await self._session.execute(
            update(TrackModel)
            .where(TrackModel.id == track_id)
            .values(title=title, performer=performer, search_key=track_key(performer, title))
        )
        await self._session.commit()

    async def increment_play_count(self, track_id: int) -> None:
        await self._session.execute(
            update(TrackModel)
            .where(TrackModel.id == track_id)
            .values(play_count=TrackModel.play_count + 1)
        )
        await self._session.commit()

    async def hide(self, track_id: int) -> bool:
        changed = await rowcount(
            self._session,
            update(TrackModel).where(TrackModel.id == track_id, _visible).values(is_hidden=True),
        )
        await self._session.commit()
        return changed == 1

    @staticmethod
    def _played_in(since: datetime, until: datetime) -> tuple[ColumnElement[bool], ...]:
        return (
            UserEventModel.kind == EventKind.TRACK_PLAY.value,
            UserEventModel.created_at >= since,
            UserEventModel.created_at < until,
            _visible,
        )

    async def top_tracks(self, since: datetime, until: datetime, limit: int) -> list[Track]:
        listeners = func.count(func.distinct(UserEventModel.user_id))
        stmt = (
            select(TrackModel)
            .join(UserEventModel, TrackModel.id == UserEventModel.meta.cast(Integer))
            .where(*self._played_in(since, until))
            .group_by(TrackModel.id)
            .order_by(listeners.desc(), TrackModel.id.desc())
            .limit(limit)
        )
        return [_track_to_domain(model) for model in await self._session.scalars(stmt)]

    async def top_played(self, since: datetime, until: datetime, limit: int) -> list[ChartEntry]:
        # Журнал прослушиваний, а не `play_count`: счётчик копится за всё время, и хит
        # прошлого года стоял бы первым вечно. Считаем РАЗНЫХ людей — один человек,
        # гоняющий трек по кругу, не делает его хитом.
        listeners = func.count(func.distinct(UserEventModel.user_id))
        stmt = (
            select(TrackModel.title, TrackModel.performer, listeners)
            .join(TrackModel, TrackModel.id == UserEventModel.meta.cast(Integer))
            .where(*self._played_in(since, until))
            .group_by(TrackModel.id, TrackModel.title, TrackModel.performer)
            .order_by(listeners.desc(), TrackModel.id.desc())
            .limit(limit)
        )
        rows = await self._session.execute(stmt)
        return [ChartEntry(title, performer, int(plays)) for title, performer, plays in rows]

    async def count_added(self, since: datetime, until: datetime) -> int:
        total = await self._session.scalar(
            select(func.count()).select_from(TrackModel).where(
                TrackModel.created_at >= since, TrackModel.created_at < until, _visible
            )
        )
        return int(total or 0)


    async def count_uploaded(self, uploader_id: int) -> int:
        total = await self._session.scalar(
            select(func.count()).select_from(TrackModel)
            .where(TrackModel.uploader_id == uploader_id, _visible)
        )
        return int(total or 0)

    async def stats(self, track_id: int) -> TrackStats:
        listeners = await self._session.scalar(
            select(func.count(func.distinct(UserEventModel.user_id))).where(
                UserEventModel.kind == EventKind.TRACK_PLAY.value,
                UserEventModel.meta == str(track_id),
            )
        )
        playlists = await self._session.scalar(
            select(func.count()).select_from(PlaylistTrackModel)
            .where(PlaylistTrackModel.track_id == track_id)
        )
        saves = await self._session.scalar(
            select(TrackModel.saves_count).where(TrackModel.id == track_id)
        )
        return TrackStats(int(listeners or 0), int(playlists or 0), int(saves or 0))

    async def by_performer(self, performer_key: str, limit: int) -> list[Track]:
        if not performer_key:
            return []
        stmt = (
            select(TrackModel)
            .where(_visible, TrackModel.search_key.startswith(f"{performer_key} "))
            .order_by((TrackModel.play_count + TrackModel.saves_count * 3).desc(), TrackModel.id)
            .limit(limit * 3)
        )
        # Ключ «a b название» начинается и с «a » — точное имя исполнителя сверяем здесь.
        found = [_track_to_domain(m) for m in await self._session.scalars(stmt)]
        return [t for t in found if fold(t.performer) == performer_key][:limit]

    async def co_listened(self, track_id: int, limit: int) -> list[Track]:
        mine = PlaylistTrackModel.__table__.alias("mine")
        other = PlaylistTrackModel.__table__.alias("other")
        together = func.count().label("together")
        pairs = (
            select(other.c.track_id, together)
            .select_from(mine.join(other, mine.c.playlist_id == other.c.playlist_id))
            .where(mine.c.track_id == track_id, other.c.track_id != track_id)
            .group_by(other.c.track_id)
            .subquery()
        )
        stmt = (
            select(TrackModel)
            .join(pairs, pairs.c.track_id == TrackModel.id)
            .where(_visible)
            .order_by(pairs.c.together.desc(), TrackModel.play_count.desc(), TrackModel.id)
            .limit(limit)
        )
        return [_track_to_domain(m) for m in await self._session.scalars(stmt)]

    async def performers(self, limit: int) -> list[tuple[str, int]]:
        count = func.count().label("tracks")
        rows = await self._session.execute(
            select(TrackModel.performer, count)
            .where(_visible)
            .group_by(TrackModel.performer)
            .order_by(count.desc(), TrackModel.performer)
            .limit(limit)
        )
        return [(str(name), int(total)) for name, total in rows]

    async def list_all(self) -> list[Track]:
        stmt = select(TrackModel).where(_visible).order_by(TrackModel.id)
        return [_track_to_domain(m) for m in await self._session.scalars(stmt)]


class PgLibraryRepository:
    """Коллекция + денормализованный `tracks.saves_count` (двигается только по факту)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user_id: int, track_id: int, at: datetime) -> bool:
        stmt = (
            pg_insert(UserTrackModel)
            .values(user_id=user_id, track_id=track_id, added_at=at)
            .on_conflict_do_nothing(index_elements=["user_id", "track_id"])
        )
        added = await rowcount(self._session, stmt) == 1
        if added:
            await self._session.execute(
                update(TrackModel)
                .where(TrackModel.id == track_id)
                .values(saves_count=TrackModel.saves_count + 1)
            )
        await self._session.commit()
        return added

    async def remove(self, user_id: int, track_id: int) -> bool:
        removed = await rowcount(
            self._session,
            delete(UserTrackModel).where(
                UserTrackModel.user_id == user_id, UserTrackModel.track_id == track_id
            ),
        ) == 1
        if removed:
            await self._session.execute(
                update(TrackModel)
                .where(TrackModel.id == track_id)
                .values(saves_count=func.greatest(TrackModel.saves_count - 1, 0))
            )
        await self._session.commit()
        return removed

    async def list_for_user(self, user_id: int, limit: int, offset: int = 0) -> list[Track]:
        stmt = (
            select(TrackModel)
            .join(UserTrackModel, UserTrackModel.track_id == TrackModel.id)
            .where(UserTrackModel.user_id == user_id, _visible)
            .order_by(UserTrackModel.added_at.desc(), TrackModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_track_to_domain(model) for model in await self._session.scalars(stmt)]

    async def list_ids(self, user_id: int) -> list[int]:
        stmt = select(UserTrackModel.track_id).where(UserTrackModel.user_id == user_id)
        return list(await self._session.scalars(stmt))


class PgPlaylistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, model: PlaylistModel) -> Playlist:
        return Playlist(
            id=model.id,
            owner_id=model.owner_id,
            title=model.title,
            share_code=model.share_code,
            track_count=model.track_count,
            is_public=model.is_public,
            saves_count=model.saves_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def _one(self, model: PlaylistModel | None) -> Playlist | None:
        return self._to_domain(model) if model is not None else None

    async def create(self, playlist: Playlist) -> Playlist:
        assert playlist.created_at is not None
        model = PlaylistModel(
            owner_id=playlist.owner_id,
            title=playlist.title,
            share_code=playlist.share_code,
            track_count=0,
            created_at=playlist.created_at,
            updated_at=playlist.created_at,
        )
        self._session.add(model)
        await self._session.commit()
        return self._to_domain(model)

    async def get(self, playlist_id: int) -> Playlist | None:
        return await self._one(await self._session.get(PlaylistModel, playlist_id))

    async def by_share_code(self, share_code: str) -> Playlist | None:
        model = await self._session.scalar(
            select(PlaylistModel).where(PlaylistModel.share_code == share_code)
        )
        return await self._one(model)

    async def list_for_owner(self, owner_id: int) -> list[Playlist]:
        models = list(await self._session.scalars(
            select(PlaylistModel)
            .where(PlaylistModel.owner_id == owner_id)
            .order_by(PlaylistModel.updated_at.desc(), PlaylistModel.id.desc())
        ))
        return [self._to_domain(model) for model in models]

    async def count_for_owner(self, owner_id: int) -> int:
        total = await self._session.scalar(
            select(func.count())
            .select_from(PlaylistModel)
            .where(PlaylistModel.owner_id == owner_id)
        )
        return int(total or 0)

    async def rename(self, playlist_id: int, title: str, at: datetime) -> None:
        await self._session.execute(
            update(PlaylistModel)
            .where(PlaylistModel.id == playlist_id)
            .values(title=title, updated_at=at)
        )
        await self._session.commit()

    async def set_public(self, playlist_id: int, is_public: bool, at: datetime) -> None:
        await self._session.execute(
            update(PlaylistModel)
            .where(PlaylistModel.id == playlist_id)
            .values(is_public=is_public, updated_at=at)
        )
        await self._session.commit()

    async def list_public(self, limit: int) -> list[Playlist]:
        models = await self._session.scalars(
            select(PlaylistModel)
            .where(PlaylistModel.is_public.is_(True), PlaylistModel.track_count > 0)
            .order_by(
                PlaylistModel.saves_count.desc(),
                PlaylistModel.updated_at.desc(),
                PlaylistModel.id.desc(),
            )
            .limit(limit)
        )
        return [self._to_domain(model) for model in models]

    async def public_with_track(self, track_id: int, limit: int) -> list[Playlist]:
        models = await self._session.scalars(
            select(PlaylistModel)
            .join(PlaylistTrackModel, PlaylistTrackModel.playlist_id == PlaylistModel.id)
            .where(PlaylistModel.is_public.is_(True), PlaylistTrackModel.track_id == track_id)
            .order_by(PlaylistModel.saves_count.desc(), PlaylistModel.id.desc())
            .limit(limit)
        )
        return [self._to_domain(model) for model in models]

    async def increment_saves(self, playlist_id: int) -> None:
        await self._session.execute(
            update(PlaylistModel)
            .where(PlaylistModel.id == playlist_id)
            .values(saves_count=PlaylistModel.saves_count + 1)
        )
        await self._session.commit()

    async def delete(self, playlist_id: int) -> None:
        await self._session.execute(delete(PlaylistModel).where(PlaylistModel.id == playlist_id))
        await self._session.commit()

    async def _lock(self, playlist_id: int) -> PlaylistModel | None:
        # Строка плейлиста под FOR UPDATE: два одновременных «добавить» иначе взяли бы
        # одну и ту же позицию и оба прошли бы проверку предела.
        return await self._session.scalar(
            select(PlaylistModel).where(PlaylistModel.id == playlist_id).with_for_update()
        )

    async def _next_position(self, playlist_id: int) -> int:
        last = await self._session.scalar(
            select(func.max(PlaylistTrackModel.position))
            .where(PlaylistTrackModel.playlist_id == playlist_id)
        )
        return int(last or 0) + 1

    async def add_track(
        self, playlist_id: int, track_id: int, at: datetime, limit: int
    ) -> PlaylistAddOutcome:
        added = await self.add_tracks(playlist_id, [track_id], at, limit)
        if added:
            return PlaylistAddOutcome.ADDED
        present = await self._session.scalar(
            select(PlaylistTrackModel.track_id).where(
                PlaylistTrackModel.playlist_id == playlist_id,
                PlaylistTrackModel.track_id == track_id,
            )
        )
        return PlaylistAddOutcome.DUPLICATE if present is not None else PlaylistAddOutcome.FULL

    async def add_tracks(
        self, playlist_id: int, track_ids: Sequence[int], at: datetime, limit: int
    ) -> int:
        playlist = await self._lock(playlist_id)
        if playlist is None:
            await self._session.rollback()
            return 0
        position = await self._next_position(playlist_id)
        room = max(limit - playlist.track_count, 0)
        added = 0
        for track_id in dict.fromkeys(track_ids):
            if added >= room:
                break
            inserted = await rowcount(
                self._session,
                pg_insert(PlaylistTrackModel)
                .values(playlist_id=playlist_id, track_id=track_id, position=position, added_at=at)
                .on_conflict_do_nothing(index_elements=["playlist_id", "track_id"]),
            )
            if inserted:
                added += 1
                position += 1
        if added:
            playlist.track_count += added
            playlist.updated_at = at
        await self._session.commit()
        return added

    async def remove_track(self, playlist_id: int, track_id: int, at: datetime) -> bool:
        playlist = await self._lock(playlist_id)
        if playlist is None:
            await self._session.rollback()
            return False
        removed = await rowcount(
            self._session,
            delete(PlaylistTrackModel).where(
                PlaylistTrackModel.playlist_id == playlist_id,
                PlaylistTrackModel.track_id == track_id,
            ),
        ) == 1
        if removed:
            playlist.track_count = max(playlist.track_count - 1, 0)
            playlist.updated_at = at
        await self._session.commit()
        return removed

    async def reorder(self, playlist_id: int, track_ids: Sequence[int], at: datetime) -> bool:
        playlist = await self._lock(playlist_id)
        if playlist is None:
            await self._session.rollback()
            return False
        current = await self.track_ids(playlist_id)
        # Порядок принимается только целиком и только для того же набора: экран, открытый
        # до чужого удаления или добавления, не должен молча терять или дублировать треки.
        if sorted(current) != sorted(track_ids) or len(set(track_ids)) != len(track_ids):
            await self._session.rollback()
            return False
        for position, track_id in enumerate(track_ids, start=1):
            await self._session.execute(
                update(PlaylistTrackModel)
                .where(
                    PlaylistTrackModel.playlist_id == playlist_id,
                    PlaylistTrackModel.track_id == track_id,
                )
                .values(position=position)
            )
        playlist.updated_at = at
        await self._session.commit()
        return True

    async def track_ids(self, playlist_id: int) -> list[int]:
        stmt = (
            select(PlaylistTrackModel.track_id)
            .where(PlaylistTrackModel.playlist_id == playlist_id)
            .order_by(PlaylistTrackModel.position)
        )
        return list(await self._session.scalars(stmt))


class PgMusicRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def vote(self, user_id: int, key: str, query: str, at: datetime) -> int:
        upsert = pg_insert(MusicRequestModel).values(
            query_key=key, query=query, votes_count=0, created_at=at, requested_at=at
        )
        # Повторный запрос уже закрытой песни снова открывает его: раз ищут — значит
        # найденный трек скрыли или он оказался не тем.
        request_id = await self._session.scalar(
            upsert.on_conflict_do_update(
                index_elements=["query_key"],
                set_={"requested_at": at, "fulfilled_at": None},
            ).returning(MusicRequestModel.id)
        )
        voted = await rowcount(
            self._session,
            pg_insert(MusicRequestVoteModel)
            .values(request_id=request_id, user_id=user_id)
            .on_conflict_do_nothing(index_elements=["request_id", "user_id"]),
        )
        if voted:
            await self._session.execute(
                update(MusicRequestModel)
                .where(MusicRequestModel.id == request_id)
                .values(votes_count=MusicRequestModel.votes_count + 1)
            )
        votes = await self._session.scalar(
            select(MusicRequestModel.votes_count).where(MusicRequestModel.id == request_id)
        )
        await self._session.commit()
        return int(votes or 0)

    async def list_open(self, limit: int) -> list[MusicRequest]:
        stmt = (
            select(MusicRequestModel)
            .where(MusicRequestModel.fulfilled_at.is_(None))
            .order_by(
                MusicRequestModel.votes_count.desc(),
                MusicRequestModel.requested_at.desc(),
            )
            .limit(limit)
        )
        return [
            MusicRequest(model.query, model.votes_count, model.requested_at)
            for model in await self._session.scalars(stmt)
        ]

    async def fulfil(self, keys: Sequence[str], at: datetime) -> list[int]:
        if not keys:
            return []
        closed = list(await self._session.scalars(
            update(MusicRequestModel)
            .where(
                MusicRequestModel.query_key.in_(list(keys)),
                MusicRequestModel.fulfilled_at.is_(None),
            )
            .values(fulfilled_at=at)
            .returning(MusicRequestModel.id)
        ))
        voters: list[int] = []
        if closed:
            voters = list(await self._session.scalars(
                select(MusicRequestVoteModel.user_id)
                .where(MusicRequestVoteModel.request_id.in_(closed))
                .distinct()
            ))
        await self._session.commit()
        return voters


class PgMusicChartLog:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def posted(self, week: date) -> bool:
        found = await self._session.scalar(
            select(MusicChartPostModel.week).where(MusicChartPostModel.week == week)
        )
        return found is not None

    async def record(self, week: date, message_id: int, at: datetime) -> None:
        await self._session.execute(
            pg_insert(MusicChartPostModel)
            .values(week=week, channel_message_id=message_id, posted_at=at)
            .on_conflict_do_nothing(index_elements=["week"])
        )
        await self._session.commit()
