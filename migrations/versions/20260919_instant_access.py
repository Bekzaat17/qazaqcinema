"""Мгновенный доступ по чеку: отметка о выдаче на заявке

`payment_requests.granted_at` — когда по этой заявке открыли доступ, не дожидаясь
модератора. NULL значит «не открывали»: так заявка, пришедшая старым путём (человек с
тремя отказами ждёт решения руками), отличается от выданной авансом. По этой же колонке
модерация решает, что делает кнопка: ✅ по выданной заявке не выдаёт подписку второй раз,
а ❌ по ней забирает доступ обратно.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-09-19

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payment_requests",
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Под ежечасное напоминание админам: «висящие заявки такого-то возраста».
    op.create_index(
        "ix_payment_requests_status_created_at",
        "payment_requests",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_payment_requests_status_created_at", "payment_requests")
    op.drop_column("payment_requests", "granted_at")
