"""Комнаты настольной игры и однократные награды победителям."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a5b6c7d8e9f0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "board_rooms",
        sa.Column("code", sa.String(10), primary_key=True),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("members", postgresql.JSONB(), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "board_awards",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.telegram_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("scenario_id", sa.String(48), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("board_awards")
    op.drop_table("board_rooms")
