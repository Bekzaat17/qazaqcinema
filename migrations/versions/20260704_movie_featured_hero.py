"""movie featured flag + hero banner url

Флаг `is_featured` (курируется в визарде /add — «показывать на hero главной») и
`hero_image_url` (горизонтальный баннер 3:2 для hero). Backfill существующих строк:
is_featured = false (через server_default), hero_image_url = NULL.

Revision ID: a1b2c3d4e5f6
Revises: b7f3a9c2d1e4
Create Date: 2026-07-04

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "b7f3a9c2d1e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "movies",
        sa.Column(
            "is_featured",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column("movies", sa.Column("hero_image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("movies", "hero_image_url")
    op.drop_column("movies", "is_featured")
