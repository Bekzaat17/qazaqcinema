"""movie multilingual titles + trigram search

Мультиязычные названия фильма (title_kk / title_ru / title_original), created_at и
поисковая инфраструктура pg_trgm + unaccent.

Написано вручную (не autogenerate): rename колонки, расширения, immutable-враппер
`f_unaccent` и GIN-trgm индексы Alembic сам не генерирует.

Зачем f_unaccent: stock `unaccent()` помечен STABLE, в индекс по выражению его класть
нельзя — нужна IMMUTABLE-обёртка. Тот же `f_unaccent` используется и в запросе поиска
(`PgMovieRepository.search`), и в индексе — иначе планировщик индекс не задействует.

Revision ID: b7f3a9c2d1e4
Revises: c2d3c2c343d2
Create Date: 2026-06-28

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7f3a9c2d1e4"
down_revision: str | None = "c2d3c2c343d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TRGM_INDEXES = ("title_kk", "title_ru", "title_original")


def upgrade() -> None:
    # --- мультиязычные названия + дата добавления ---
    op.alter_column("movies", "title", new_column_name="title_kk")
    op.add_column("movies", sa.Column("title_ru", sa.String(length=255), nullable=True))
    op.add_column("movies", sa.Column("title_original", sa.String(length=255), nullable=True))
    op.add_column(
        "movies",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # --- поисковая инфраструктура (pg_trgm + unaccent) ---
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    # 2-арг форма unaccent('unaccent', $1) позволяет пометить обёртку IMMUTABLE.
    op.execute(
        "CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT "
        "AS $$ SELECT public.unaccent('public.unaccent', $1) $$"
    )
    for column in _TRGM_INDEXES:
        op.execute(
            f"CREATE INDEX ix_movies_{column}_trgm ON movies "
            f"USING gin (f_unaccent({column}) gin_trgm_ops)"
        )


def downgrade() -> None:
    for column in _TRGM_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS ix_movies_{column}_trgm")
    op.execute("DROP FUNCTION IF EXISTS f_unaccent(text)")
    op.drop_column("movies", "created_at")
    op.drop_column("movies", "title_original")
    op.drop_column("movies", "title_ru")
    op.alter_column("movies", "title_kk", new_column_name="title")
    # Расширения pg_trgm/unaccent оставляем — могут использоваться другими объектами.
