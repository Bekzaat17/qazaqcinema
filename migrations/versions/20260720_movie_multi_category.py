"""movie multi-category: category -> categories text[]

Мультикатегорийность: один фильм может относиться к нескольким категориям
(например fantasy + disney). Одиночная колонка `category VARCHAR(32)` заменяется
массивом `categories VARCHAR(32)[]` с GIN-индексом под overlap-запросы
(`categories && ARRAY[...]` в браузинге каталога). Существующие строки
бэкфилятся в одноэлементный массив `ARRAY[category]` — данные не теряются.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-20

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) Новая колонка-массив (пока nullable — заполним бэкфиллом).
    op.add_column(
        "movies",
        sa.Column("categories", postgresql.ARRAY(sa.String(length=32)), nullable=True),
    )
    # 2) Бэкфилл: каждая существующая категория → одноэлементный массив.
    op.execute("UPDATE movies SET categories = ARRAY[category] WHERE category IS NOT NULL")
    op.execute("UPDATE movies SET categories = '{}' WHERE categories IS NULL")
    # 3) Теперь колонка обязательна.
    op.alter_column("movies", "categories", nullable=False)
    # 4) Старую одиночную колонку (и её btree-индекс) убираем.
    op.drop_index("ix_movies_category", table_name="movies")
    op.drop_column("movies", "category")
    # 5) GIN-индекс под overlap/any по массиву категорий.
    op.create_index(
        "ix_movies_categories_gin",
        "movies",
        ["categories"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_movies_categories_gin", table_name="movies")
    op.add_column(
        "movies",
        sa.Column("category", sa.String(length=32), nullable=True),
    )
    # Обратно берём первый элемент массива (потеря доп. категорий — неизбежна при откате).
    op.execute("UPDATE movies SET category = categories[1]")
    op.alter_column("movies", "category", nullable=False)
    op.create_index("ix_movies_category", "movies", ["category"])
    op.drop_column("movies", "categories")
