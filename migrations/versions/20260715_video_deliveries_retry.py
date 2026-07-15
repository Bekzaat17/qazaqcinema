"""video_deliveries: ретраи удаления (attempts + next_attempt_at)

Чистка выданных видео теперь смотрит на ОТВЕТ Telegram и различает постоянный отказ
(>48 ч, сообщения нет, бот заблокирован → строку сносим сразу) от временного сбоя
(сеть/5xx → повторяем). Для повторов нужны две колонки:

  attempts        — сколько раз подряд был ВРЕМЕННЫЙ сбой; MAX_ATTEMPTS → сдаёмся.
  next_attempt_at — когда пробовать снова; NULL = «сразу» (обычный случай).

next_attempt_at — не украшение, а условие корректности цикла: без него сбойная пачка
возвращалась бы тем же запросом внутри одного прогона (вечный цикл) и забивала бы голову
очереди, не пуская свежие выдачи на удаление. Срок в будущем убирает строку из выборки.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-15

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # server_default="0" — у существующих строк колонка не может быть NULL при NOT NULL.
    op.add_column(
        "video_deliveries",
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "video_deliveries",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("video_deliveries", "next_attempt_at")
    op.drop_column("video_deliveries", "attempts")
