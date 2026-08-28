"""daily_reports snapshot history + milestones feed

Фундамент истории аналитики (решение 2026-08-28): ежевечерний отчёт раньше только
уходил в Telegram и пропадал — сравнить «месяц назад / сегодня» было нечем, кроме
пересчёта сырых `user_events` (а размер каталога/аудитории НА ТОТ момент к тому же
пересчётом уже не восстановить, `movies`/`users` растут). `daily_reports` — снимок
раз в сутки (upsert по `day`), пишет `AnalyticsService.daily_report` тем же вызовом,
которым собирается текст для админов.

`milestones` — лента вех роста («вкатили фильм дня», «убрали баннер hero») для
команды `/milestone`. НЕ состояние «текущая модель»: подарочный фильм и фильм дня
работают ОДНОВРЕМЕННО (см. порядок оснований в `PlaybackService`), одно значение на
дату было бы неправдой — вместо этого метки на шкале, сравнивать «до/после» человек
делает сам глазами по датам.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-08-28

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: str | None = "b4c5d6e7f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_reports",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("users_total", sa.Integer(), nullable=False),
        sa.Column("users_new", sa.Integer(), nullable=False),
        sa.Column("subs_active", sa.Integer(), nullable=False),
        sa.Column("catalog_size", sa.Integer(), nullable=False),
        sa.Column("opens_total", sa.Integer(), nullable=False),
        sa.Column("opens_unique", sa.Integer(), nullable=False),
        sa.Column("starts", sa.Integer(), nullable=False),
        sa.Column("plays", sa.Integer(), nullable=False),
        sa.Column("free_plays", sa.Integer(), nullable=False),
        sa.Column("daily_plays", sa.Integer(), nullable=False),
        sa.Column("paywalls", sa.Integer(), nullable=False),
        sa.Column("subscribes", sa.Integer(), nullable=False),
        sa.Column("expires", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("day"),
    )
    op.create_table(
        "milestones",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_milestones_occurred_at", "milestones", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_milestones_occurred_at", table_name="milestones")
    op.drop_table("milestones")
    op.drop_table("daily_reports")
