"""daily_reports: метрики канала и недельного выбора

Четыре колонки в снимок: `channel_gates` (сколько людей уткнулись в требование подписки),
`weekly_picks` (сколько взяли фильм на неделю), `weekly_plays` (сколько смотрели, включая
пересмотры) и `channel_members` (подписчиков у канала на конец дня).

Первые три — счётчики: `server_default 0`, старые снимки честно читаются как «этого тогда
не было». `channel_members` — НУЛЛУЕМАЯ: ноль подписчиков и «Telegram не ответил» это
разные вещи, и в отчёте вторая обязана выглядеть как пропуск строки, а не как обвал
аудитории до нуля.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-09-17

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b0c1d2e3f4a5"
down_revision: str | None = "a9b0c1d2e3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COUNTERS = ("channel_gates", "weekly_picks", "weekly_plays")


def upgrade() -> None:
    for name in _COUNTERS:
        op.add_column(
            "daily_reports",
            sa.Column(name, sa.Integer(), server_default=sa.text("0"), nullable=False),
        )
    op.add_column("daily_reports", sa.Column("channel_members", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("daily_reports", "channel_members")
    for name in reversed(_COUNTERS):
        op.drop_column("daily_reports", name)
