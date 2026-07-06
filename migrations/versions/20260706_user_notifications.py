"""user notifications opt-out flag

Флаг `notifications_enabled` (рассылки о новинках — Фаза 12; opt-out, по умолчанию ВКЛ).
Backfill существующих строк в True через server_default — отдельный UPDATE не нужен.

Revision ID: c7e8f9a0b1c2
Revises: a1b2c3d4e5f6
Create Date: 2026-07-06

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e8f9a0b1c2"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "notifications_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "notifications_enabled")
