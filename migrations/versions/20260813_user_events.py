"""user events journal + users.created_at

Журнал значимых действий (`user_events`: start/open/play/subscribe/expire) и дата
появления юзера. На них считается ежевечерний отчёт админам и любая будущая аналитика.

`users.created_at` заполняется server_default'ом: у существующих строк точной даты
взять неоткуда, поэтому им проставится момент миграции (backfill без отдельного UPDATE).

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-08-13

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "user_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        # kind — VARCHAR, не PG-ENUM: новый вид события не требует миграции типа.
        sa.Column("kind", sa.String(length=32), nullable=False),
        # meta — свободная привязка: id фильма у play, slug тарифа у subscribe.
        sa.Column("meta", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_events_user_id", "user_events", ["user_id"])
    # Составной под запросы отчёта: «событий вида X за период».
    op.create_index("ix_user_events_kind_created_at", "user_events", ["kind", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_user_events_kind_created_at", table_name="user_events")
    op.drop_index("ix_user_events_user_id", table_name="user_events")
    op.drop_table("user_events")
    op.drop_column("users", "created_at")
