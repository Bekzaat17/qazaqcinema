"""Подарочный первый фильм + избранное.

Две связанные вещи одной миграцией, потому что обе обслуживают одну воронку «сначала
ценность, потом оплата»:

  • `users.free_view_used_at` / `free_view_movie_id` — право на ОДИН бесплатный фильм.
    Это право доступа, а не статистика, поэтому живёт явной колонкой, а не выводится из
    `user_events`: журнал намеренно fail-open (сбой записи не роняет выдачу видео), и
    вывод «смотрел ли уже» из него раздавал бы вторую халяву на каждом сбое.

  • `favorites` + `movies.favorites_count` — личные списки и денормализованный счётчик
    под сортировку «Танымал» (формула в `domain/catalog/popularity.py`).

БЭКФИЛЛ: тем, кто когда-либо платил (`expires_at IS NOT NULL`), подарок помечается
использованным. Иначе после истечения подписки платящий получил бы бесплатный фильм
вместо продления — воронка кормила бы отток. `free_view_movie_id` у них остаётся NULL:
конкретного подаренного фильма не было, и «бесплатно пересмотреть» им нечего.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-17

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- подарочный первый фильм ---------------------------------------------------
    op.add_column("users", sa.Column("free_view_used_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("free_view_movie_id", sa.Integer(), nullable=True))
    # Плативших исключаем из подарка (см. шапку). Метка — момент миграции: точной даты
    # «когда он потратил подарок» не существует, подарка у них и не было.
    op.execute(
        "UPDATE users SET free_view_used_at = now() WHERE expires_at IS NOT NULL"
    )

    # --- избранное -----------------------------------------------------------------
    op.create_table(
        "favorites",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.telegram_id"), nullable=False),
        sa.Column(
            "movie_id",
            sa.Integer(),
            sa.ForeignKey("movies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        # PK (user_id, movie_id) — он же гарантия «одна звезда на фильм».
        sa.PrimaryKeyConstraint("user_id", "movie_id"),
    )
    op.create_index("ix_favorites_user_created_at", "favorites", ["user_id", "created_at"])

    op.add_column(
        "movies",
        sa.Column(
            "favorites_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("movies", "favorites_count")
    op.drop_index("ix_favorites_user_created_at", table_name="favorites")
    op.drop_table("favorites")
    op.drop_column("users", "free_view_movie_id")
    op.drop_column("users", "free_view_used_at")
