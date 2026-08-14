"""fuzzystrmatch для поиска с опечатками

Триграммной похожести (`pg_trgm`) не хватает на КОРОТКИХ названиях: у «шрек» и «шрик»
similarity = 0.25, то есть ниже рабочего порога 0.3 — опечатка в середине короткого слова
съедает сразу два общих триграмма из восьми. На длинных словах проблемы нет («наруто» vs
«нарута» = 0.556), поэтому дыра и была незаметна.

`levenshtein` из fuzzystrmatch считает ровно то, что нужно человеку: «сколько букв не
совпало». Расширение — из стандартной поставки contrib, отдельных зависимостей не тянет.

Откат намеренно НЕ удаляет расширение: оно общее для базы, и `DROP EXTENSION` сломал бы
всё, что успело им воспользоваться. Расширение без индексов и колонок ничего не весит.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-14

"""
from collections.abc import Sequence

from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS fuzzystrmatch")


def downgrade() -> None:
    pass
