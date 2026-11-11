"""Completed online games: personal history and standings."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b6c7d8e9f0a1"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "board_results",
        sa.Column("code", sa.String(10), sa.ForeignKey("board_rooms.code"), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.telegram_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(24), nullable=False),
        sa.Column("scenario_id", sa.String(48), nullable=False),
        sa.Column("board_id", sa.String(48), nullable=False),
        sa.Column("rounds", sa.Integer(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("winner_name", sa.String(24), nullable=False),
        sa.Column("player_count", sa.Integer(), nullable=False),
        sa.Column("capital", sa.BigInteger(), nullable=False),
        sa.Column("won", sa.Boolean(), nullable=False),
    )
    op.create_index(
        "ix_board_results_history", "board_results", ["user_id", sa.text("finished_at DESC")]
    )


def downgrade() -> None:
    op.drop_table("board_results")
