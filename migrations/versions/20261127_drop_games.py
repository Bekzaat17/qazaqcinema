"""Удалить таблицы QazaqQuest и настольной игры: раздел заменён музыкой.

Откат не восстанавливает данные — они удаляются безвозвратно, поэтому downgrade
честно отказывает, а не создаёт пустые таблицы, которые выглядели бы как данные.
"""

from __future__ import annotations

from alembic import op

revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None

_TABLES = (
    "board_results",
    "board_awards",
    "board_rooms",
    "quest_channel_posts",
    "quest_weekly_scores",
    "quest_runs",
    "quest_players",
)


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


def downgrade() -> None:
    raise NotImplementedError("Игровые таблицы удалены вместе с данными; отката нет.")
