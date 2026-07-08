"""video deliveries (delete delivered videos on subscription expiry)

Таблица `video_deliveries` — учёт выданных подписчику видео-сообщений (chat_id +
message_id). При истечении подписки бот удаляет эти сообщения из чата, чтобы
оплаченный контент не оставался на руках навсегда (`SubscriptionService.expire_due`).

Revision ID: f1a2b3c4d5e6
Revises: d1e2f3a4b5c6
Create Date: 2026-07-08

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"]),
    )
    op.create_index(
        "ix_video_deliveries_user_id", "video_deliveries", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_video_deliveries_user_id", table_name="video_deliveries")
    op.drop_table("video_deliveries")
