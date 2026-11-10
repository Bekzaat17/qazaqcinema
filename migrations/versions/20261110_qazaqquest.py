"""QazaqQuest: суточные испытания, аул, рейтинги и журнал публикаций."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quest_players",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.telegram_id"), primary_key=True),
        sa.Column("total_xp", sa.Integer(), server_default="0", nullable=False),
        sa.Column("wood", sa.Integer(), server_default="0", nullable=False),
        sa.Column("stone", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "completed_quests", postgresql.ARRAY(sa.String(32)), server_default="{}", nullable=False
        ),
        sa.Column("buildings", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.CheckConstraint("wood >= 0 AND stone >= 0 AND total_xp >= 0", name="ck_quest_wallet"),
    )
    op.create_index(
        "ix_quest_players_ranking", "quest_players", [sa.text("total_xp DESC"), "user_id"]
    )
    op.create_table(
        "quest_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.telegram_id"), nullable=False),
        sa.Column("quest_id", sa.String(32), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("question_ids", postgresql.ARRAY(sa.String(32)), nullable=False),
        sa.Column("question_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tried", postgresql.ARRAY(sa.String(64)), server_default="{}", nullable=False),
        sa.Column("points", sa.Integer(), server_default="0", nullable=False),
        sa.UniqueConstraint("user_id", "quest_id", "day", name="uq_quest_run_daily"),
        sa.CheckConstraint("points BETWEEN 0 AND 100", name="ck_quest_run_points"),
    )
    op.create_index("ix_quest_runs_user_day", "quest_runs", ["user_id", "day"])
    op.create_table(
        "quest_weekly_scores",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.telegram_id"), primary_key=True),
        sa.Column("week", sa.Date(), primary_key=True),
        sa.Column("points", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_quest_weekly_ranking",
        "quest_weekly_scores",
        ["week", sa.text("points DESC"), "user_id"],
    )
    op.create_table(
        "quest_channel_posts",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "reserved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    for table in ("quest_channel_posts", "quest_weekly_scores", "quest_runs", "quest_players"):
        op.drop_table(table)
