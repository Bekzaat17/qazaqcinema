"""series + series_seasons; movies.season_id/episode_number

Сериалы (решение 2026-08-28): `series` — только название (группировка сезонов для
визарда `/add` и каталога). `series_seasons` — держатель постера/названия/категорий/
описания на ВСЕ свои серии (спрашивается один раз при создании сезона, как у обычного
фильма); отдельные серии внутри сезона своего названия не имеют — только номер.

`movies.season_id`/`episode_number` — NULL у обоих = обычный самостоятельный фильм,
существующие строки такими и остаются (никакого backfill не требуется).

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-08-28

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4c5d6e7f8a9"
down_revision: str | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "series",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title_kk", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "series_seasons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("season_number", sa.Integer(), nullable=False),
        sa.Column("poster_url", sa.Text(), nullable=False),
        sa.Column("title_kk", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("categories", postgresql.ARRAY(sa.String(length=32)), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # Один и тот же номер сезона у сериала не заводим дважды.
        sa.UniqueConstraint("series_id", "season_number", name="uq_season_series_number"),
    )
    op.create_index("ix_series_seasons_series_id", "series_seasons", ["series_id"])

    op.add_column("movies", sa.Column("season_id", sa.Integer(), nullable=True))
    op.add_column("movies", sa.Column("episode_number", sa.Integer(), nullable=True))
    # ON DELETE SET NULL — снос сезона не должен утаскивать за собой серии молча
    # удалёнными; такого UI сейчас всё равно нет, но так безопаснее по умолчанию.
    op.create_foreign_key(
        "fk_movies_season_id", "movies", "series_seasons", ["season_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_movies_season_id", "movies", ["season_id"])


def downgrade() -> None:
    op.drop_index("ix_movies_season_id", table_name="movies")
    op.drop_constraint("fk_movies_season_id", "movies", type_="foreignkey")
    op.drop_column("movies", "episode_number")
    op.drop_column("movies", "season_id")
    op.drop_index("ix_series_seasons_series_id", table_name="series_seasons")
    op.drop_table("series_seasons")
    op.drop_table("series")
