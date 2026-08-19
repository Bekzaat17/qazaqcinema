"""users.bot_started_at — открыт ли чат с ботом

Telegram не позволяет боту написать первым, а видео уходит ТОЛЬКО в чат с ботом.
Люди, попавшие в Mini App по ссылке (из браузера/поиска), каталог видят, но получить
фильм не могут — до этой колонки узнать их заранее было нельзя, и человек упирался в
ошибку уже потратив подарок.

Backfill: факт открытого чата достоверно доказывают два следа — событие `start` в
журнале и любая состоявшаяся выдача видео (её приняла личка юзера). Берём МИНИМАЛЬНОЕ
время из них: это и есть момент, когда чат заведомо уже существовал.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-08-19

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: str | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("bot_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE users u
        SET bot_started_at = src.first_contact
        FROM (
            SELECT user_id, MIN(at) AS first_contact
            FROM (
                SELECT user_id, created_at AS at FROM user_events WHERE kind = 'start'
                UNION ALL
                SELECT user_id, created_at AS at FROM video_deliveries
            ) AS proof
            GROUP BY user_id
        ) AS src
        WHERE u.telegram_id = src.user_id
        """
    )


def downgrade() -> None:
    op.drop_column("users", "bot_started_at")
