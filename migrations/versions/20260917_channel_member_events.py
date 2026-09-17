"""Движение в канале: журнал подписок/отписок + две колонки в снимок отчёта

`channel_member_events` — подписался/отписался по головам (апдейты `chat_member`).
Своя таблица, а не вид `user_events`: там `user_id` — внешний ключ на `users`, а на канал
подписываются и те, кто бота ни разу не открывал. Здесь ключа нет намеренно.

`daily_reports.channel_joins` / `.channel_leaves` — счётчики, `server_default 0`: старые
снимки честно читаются как «этого тогда не считали». В отчёте при обоих нулях строка
падает на прежнюю разность снимков, а не рисует «+0 / −0» за дни, когда журнала не было.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-09-17

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b0c1d2e3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COUNTERS = ("channel_joins", "channel_leaves")


def upgrade() -> None:
    op.create_table(
        "channel_member_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("change", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_channel_member_events_user_id", "channel_member_events", ["user_id"])
    # Под единственный запрос отчёта: «сколько таких движений за сутки».
    op.create_index(
        "ix_channel_member_events_change_created_at",
        "channel_member_events",
        ["change", "created_at"],
    )
    for name in _COUNTERS:
        op.add_column(
            "daily_reports",
            sa.Column(name, sa.Integer(), server_default=sa.text("0"), nullable=False),
        )


def downgrade() -> None:
    for name in reversed(_COUNTERS):
        op.drop_column("daily_reports", name)
    op.drop_index("ix_channel_member_events_change_created_at", "channel_member_events")
    op.drop_index("ix_channel_member_events_user_id", "channel_member_events")
    op.drop_table("channel_member_events")
