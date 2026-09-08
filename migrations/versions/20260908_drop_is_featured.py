"""Снос мёртвой колонки movies.is_featured

Флаг курируемого hero: hero главной давно стал фильмом дня и берёт весь каталог по
очереди, читателей у колонки не осталось ни в коде, ни на фронте.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-08

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: str | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("movies", "is_featured")


def downgrade() -> None:
    op.add_column(
        "movies",
        sa.Column("is_featured", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
