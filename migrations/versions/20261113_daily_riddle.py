"""Три попытки для жұмбақ дня; обычные квизы сохраняют первый ответ."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quiz_answers",
        sa.Column("attempt_count", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("quiz_answers", "attempt_count")
