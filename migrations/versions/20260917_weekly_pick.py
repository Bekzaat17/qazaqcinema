"""users.weekly_week / weekly_movie_id — недельный бесплатный выбор

Один фильм бесплатно на ОБЩЕЕ для всех окно (понедельник 00:00 по Алматы). Приходит на
смену одноразовому подарку (`free_view_*`): тот остаётся у тех, кто его уже потратил, —
их фильм бесплатен навсегда, и отнимать его не за что, — но новым больше не выдаётся.

Храним КЛЮЧ ОКНА (дату понедельника), а не срок. Персональный срок требовал бы джоба,
который его гасит; ключ освобождает право сам, сменой недели, без единой записи в БД.

Backfill не нужен и был бы неверен: NULL здесь и значит «не выбирал», а прошлые подарки
живут в своих колонках и к этому окну отношения не имеют.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-09-17

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: str | None = "f8a9b0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("weekly_week", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("weekly_movie_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "weekly_movie_id")
    op.drop_column("users", "weekly_week")
