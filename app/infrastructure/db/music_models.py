"""ORM-модели музыкального раздела. Аудио на сервере не хранится — только метаданные.

⚠️ Триграммные индексы поиска (`f_unaccent(title) gin_trgm_ops`) объявлены только в
миграции: `create_all` в тестах запускается раньше, чем появляется функция `f_unaccent`,
и индекс по выражению с ней здесь уронил бы создание схемы.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class TrackModel(Base):
    """Трек общего каталога: только сведения и `file_id` — сам файл живёт в Telegram.

    `file_unique_id` UNIQUE — один и тот же файл, пересланный десятью людьми, остаётся
    одной строкой. `uploader_id` без FK на `users`: человек мог прислать аудио раньше,
    чем попал в таблицу пользователей, и терять из-за этого трек незачем.
    """

    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    performer: Mapped[str] = mapped_column(String(128))
    # `domain/music/search.fold(исполнитель + название)` — по нему ищут и склеивают дубли.
    search_key: Mapped[str] = mapped_column(String(300), index=True, server_default="")
    duration_sec: Mapped[int] = mapped_column(Integer)
    telegram_file_id: Mapped[str] = mapped_column(String(255))
    file_unique_id: Mapped[str] = mapped_column(String(64), unique=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    archive_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uploader_id: Mapped[int] = mapped_column(BigInteger, index=True)
    play_count: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    saves_count: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    is_hidden: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserTrackModel(Base):
    """«Менің музыкам»: составной ключ сам гарантирует «один трек — одна запись»."""

    __tablename__ = "user_tracks"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_user_tracks_user_added", "user_id", "added_at"),)


class PlaylistModel(Base):
    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(64))
    share_code: Mapped[str] = mapped_column(String(16), unique=True)
    track_count: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    saves_count: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_playlists_public", "is_public", "saves_count"),)


class PlaylistTrackModel(Base):
    """Трек в плейлисте. `position` растёт: новые — в конец, порядок стабилен."""

    __tablename__ = "playlist_tracks"

    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    track_id: Mapped[int] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    position: Mapped[int] = mapped_column(Integer)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_playlist_tracks_order", "playlist_id", "position"),)


class MusicRequestModel(Base):
    """«Этой песни нет»: ключ — нормализованный запрос, один на все написания."""

    __tablename__ = "music_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    query_key: Mapped[str] = mapped_column(String(128), unique=True)
    query: Mapped[str] = mapped_column(String(128))
    votes_count: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MusicRequestVoteModel(Base):
    """Голос за запрос: считаем РАЗНЫХ людей, а не нажатия одного."""

    __tablename__ = "music_request_votes"

    request_id: Mapped[int] = mapped_column(
        ForeignKey("music_requests.id", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)


class MusicChartPostModel(Base):
    """Хит-парад недели в канале: неделя — первичный ключ, второй пост схема не пустит."""

    __tablename__ = "music_chart_posts"

    week: Mapped[date] = mapped_column(Date, primary_key=True)
    channel_message_id: Mapped[int] = mapped_column(BigInteger)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
