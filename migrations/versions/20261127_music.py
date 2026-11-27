"""Музыка: общий каталог треков, коллекции, плейлисты, запросы и хит-парад недели."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e9f0a1b2c3d4"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "tracks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("performer", sa.String(128), nullable=False),
        sa.Column("duration_sec", sa.Integer(), nullable=False),
        sa.Column("telegram_file_id", sa.String(255), nullable=False),
        sa.Column("file_unique_id", sa.String(64), nullable=False, unique=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("mime_type", sa.String(64), nullable=True),
        sa.Column("archive_message_id", sa.BigInteger(), nullable=True),
        sa.Column("uploader_id", sa.BigInteger(), nullable=False),
        sa.Column("play_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("saves_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_hidden", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tracks_uploader_id", "tracks", ["uploader_id"])
    # Поиск по названию и исполнителю — тот же приём, что у фильмов (f_unaccent + trgm).
    for column in ("title", "performer"):
        op.execute(
            f"CREATE INDEX ix_tracks_{column}_trgm ON tracks "
            f"USING gin (f_unaccent({column}) gin_trgm_ops)"
        )
    op.create_table(
        "user_tracks",
        sa.Column("user_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column(
            "track_id", sa.Integer(), sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            primary_key=True, autoincrement=False,
        ),
        sa.Column("added_at", _TS, nullable=False),
    )
    op.create_index("ix_user_tracks_user_added", "user_tracks", ["user_id", "added_at"])
    op.create_table(
        "playlists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(64), nullable=False),
        sa.Column("share_code", sa.String(16), nullable=False, unique=True),
        sa.Column("track_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("saves_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", _TS, nullable=False),
        sa.Column("updated_at", _TS, nullable=False),
    )
    op.create_index("ix_playlists_owner_id", "playlists", ["owner_id"])
    op.create_index("ix_playlists_public", "playlists", ["is_public", "saves_count"])
    op.create_table(
        "playlist_tracks",
        sa.Column(
            "playlist_id", sa.Integer(), sa.ForeignKey("playlists.id", ondelete="CASCADE"),
            primary_key=True, autoincrement=False,
        ),
        sa.Column(
            "track_id", sa.Integer(), sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            primary_key=True, autoincrement=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("added_at", _TS, nullable=False),
    )
    op.create_index("ix_playlist_tracks_order", "playlist_tracks", ["playlist_id", "position"])
    op.create_table(
        "music_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("query_key", sa.String(128), nullable=False, unique=True),
        sa.Column("query", sa.String(128), nullable=False),
        sa.Column("votes_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", _TS, nullable=False),
        sa.Column("requested_at", _TS, nullable=False),
        sa.Column("fulfilled_at", _TS, nullable=True),
    )
    op.create_table(
        "music_request_votes",
        sa.Column(
            "request_id", sa.Integer(),
            sa.ForeignKey("music_requests.id", ondelete="CASCADE"),
            primary_key=True, autoincrement=False,
        ),
        sa.Column("user_id", sa.BigInteger(), primary_key=True, autoincrement=False),
    )
    op.create_table(
        "music_chart_posts",
        sa.Column("week", sa.Date(), primary_key=True),
        sa.Column("channel_message_id", sa.BigInteger(), nullable=False),
        sa.Column("posted_at", _TS, nullable=False),
    )


def downgrade() -> None:
    for table in (
        "music_chart_posts", "music_request_votes", "music_requests",
        "playlist_tracks", "playlists", "user_tracks",
    ):
        op.drop_table(table)
    for column in ("title", "performer"):
        op.execute(f"DROP INDEX IF EXISTS ix_tracks_{column}_trgm")
    op.drop_table("tracks")
