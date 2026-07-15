"""video_deliveries: индекс на created_at (ежечасная чистка по возрасту)

Выданные видео теперь удаляются НЕ только при истечении подписки, но и по возрасту —
ежечасный джоб сносит всё старше 40 ч (`VideoRetentionService.purge_stale`), потому что
Telegram не даёт боту удалить сообщение старше 48 ч. Джоб ходит запросом
`WHERE created_at < cutoff ORDER BY id LIMIT n` — под него и индекс.

Таблица невелика по построению (в ней живут лишь выдачи за последние ~40 ч), но индекс
делает чистку независимой от трафика и стоит дёшево.

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-07-15

"""
from collections.abc import Sequence

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_video_deliveries_created_at"),
        "video_deliveries",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_video_deliveries_created_at"), table_name="video_deliveries"
    )
