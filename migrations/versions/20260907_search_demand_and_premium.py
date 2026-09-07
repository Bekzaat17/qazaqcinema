"""search_queries (спрос словами) + users.is_premium

Решение 2026-09-07. До этого единственным сигналом спроса были просмотры, то есть
выбор ИЗ УЖЕ ЗАЛИТОГО, — он не отвечает на главный вопрос наполнения каталога:
«чего у нас нет». По живым данным это было особенно заметно: 175 фильмов, из них
170 детских, и «взрослое кино недобирает» невозможно было отличить от «взрослого
кино почти нет» ни одним запросом к базе.

`search_queries` — этот сигнал: что человек СПРОСИЛ и сколько по этому нашлось.
Строки с `found = 0`, отсортированные по частоте, и есть очередь на озвучку —
люди прямым текстом называют, за чем пришли и ушли ни с чем. Отдельная таблица,
а не вид `user_events`: у факта два измерения (запрос И результат), а у события
ровно одно свободное поле `meta`.

`users.is_premium` — единственный признак платёжеспособности, который Telegram
отдаёт бесплатно (приходит в подписанном initData на каждом входе). В правах
доступа не участвует; нужен, чтобы увидеть, отличается ли конверсия у тех, кто
уже платит Telegram, от тех, кто не платил никогда.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-09-07

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: str | None = "c5d6e7f8a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_queries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        # Хранится УЖЕ нормализованным (`domain/analytics/search.normalize_query`):
        # таблица существует ради частоты запроса, и без сведения регистра/пробелов
        # к одной форме топ рассыпался бы на варианты написания одного спроса.
        sa.Column("query", sa.String(length=64), nullable=False),
        # Сколько карточек нашлось. 0 — главная строка этой таблицы.
        sa.Column("found", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # Один индекс по времени: и дневное окно отчёта, и недельное окно дайджеста ходят
    # именно по нему, а группировка по `query` внутри окна идёт хэш-агрегацией — своего
    # индекса ей не нужно. Отдельный частичный индекс под `found = 0` не заводим:
    # нулевые отбираются уже внутри окна, срезанного этим индексом.
    op.create_index("ix_search_queries_created_at", "search_queries", ["created_at"])

    # server_default false → существующие 328 строк заполняются сразу, без отдельного
    # UPDATE. Для них признак просто неизвестен: Premium подтянется при первом же входе
    # человека в Mini App (`AuthService.authenticate` сверяет его на каждом логине).
    op.add_column(
        "users",
        sa.Column(
            "is_premium",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_premium")
    op.drop_index("ix_search_queries_created_at", table_name="search_queries")
    op.drop_table("search_queries")
