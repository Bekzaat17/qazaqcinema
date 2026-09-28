"""daily_reports: владельцев Telegram Premium в снимке

`users_premium` — сколько пользователей с Telegram Premium на конец дня (прокси
платёжеспособности аудитории; сам флаг `users.is_premium` собирается с 2026-09-07).
НУЛЛУЕМАЯ, как `channel_members`: у старых снимков этой цифры нет, и «не знаем» в
недельной динамике не должно читаться как «ноль премиумов».

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-09-28

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: str | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("daily_reports", sa.Column("users_premium", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("daily_reports", "users_premium")
