"""movie play_count for popularity

Счётчик просмотров `play_count` (Фаза 13): +1 при успешной выдаче видео
(`PlaybackService`), сортировка полки «Танымал» и каталога «по просмотрам».
Backfill существующих строк в 0 через server_default — отдельный UPDATE не нужен.

Revision ID: d1e2f3a4b5c6
Revises: c7e8f9a0b1c2
Create Date: 2026-07-06

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: str | None = "c7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "movies",
        sa.Column(
            "play_count",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("movies", "play_count")
