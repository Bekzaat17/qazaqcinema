"""Контент канала: content_items + channel_post_log + quiz_answers

Публичный канал ведётся сам, по недельной сетке, из
заранее заполненного пула: қара сөз, мақал, жұмбақ, атаулары, нақыл сөз — плюс квизы с
разбором. Без LLM в рантайме: контент собирается один раз в YAML и заливается сидером.

`content_items` — пул. Вид (`kind`) — ФОРМА поста, тема (`topic`) — рубрика; оба VARCHAR.
`payload` JSONB: у форм разные поля (варианты квиза, список терминов) — разреженные
колонки были бы хуже. `slug` UNIQUE — натуральный ключ сидера (upsert без дублей).

`channel_post_log` — журнал публикаций. `slot_key` UNIQUE — идемпотентность слота в
БД, не в коде: рестарт бота внутри misfire-окна не даст второго поста в канале, где
дубль увидят все подписчики.

`quiz_answers` — первый ответ каждого на каждый квиз (UNIQUE post+user). `user_id`
без FK на users: отвечающий мог никогда не запускать бота.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-09-07

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7f8a9b0c1d2"
down_revision: str | None = "d6e7f8a9b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("topic", sa.String(length=32), nullable=False),
        sa.Column("title_kk", sa.String(length=255), nullable=False),
        sa.Column("body_kk", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), server_default="", nullable=False),
        sa.Column("image_path", sa.Text(), nullable=True),
        sa.Column("image_credit", sa.Text(), server_default="", nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("scheduled_for", sa.Date(), nullable=True),
        sa.Column("last_posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("post_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_content_items_slug"),
    )
    # Ротация выбирает по форме (и теме) — индекс по kind; пул невелик (сотни строк),
    # сортировку по last_posted_at внутри формы Postgres сделает в памяти.
    op.create_index("ix_content_items_kind", "content_items", ["kind"])

    op.create_table(
        "channel_post_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slot_key", sa.String(length=64), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("channel_message_id", sa.BigInteger(), nullable=False),
        sa.Column("group_message_id", sa.BigInteger(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quiz_closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["item_id"], ["content_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot_key", name="uq_channel_post_log_slot_key"),
    )
    op.create_index("ix_channel_post_log_item_id", "channel_post_log", ["item_id"])
    # Ответ кнопкой приходит с id сообщения канала, комментарий — с id форварда в группе:
    # оба пути ищут запись по своему id.
    op.create_index(
        "ix_channel_post_log_channel_message_id", "channel_post_log", ["channel_message_id"]
    )
    op.create_index(
        "ix_channel_post_log_group_message_id", "channel_post_log", ["group_message_id"]
    )

    op.create_table(
        "quiz_answers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column("text", sa.String(length=255), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["channel_post_log.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "user_id", name="uq_quiz_answers_post_user"),
    )
    op.create_index("ix_quiz_answers_post_id", "quiz_answers", ["post_id"])


def downgrade() -> None:
    op.drop_index("ix_quiz_answers_post_id", table_name="quiz_answers")
    op.drop_table("quiz_answers")
    op.drop_index("ix_channel_post_log_group_message_id", table_name="channel_post_log")
    op.drop_index("ix_channel_post_log_channel_message_id", table_name="channel_post_log")
    op.drop_index("ix_channel_post_log_item_id", table_name="channel_post_log")
    op.drop_table("channel_post_log")
    op.drop_index("ix_content_items_kind", table_name="content_items")
    op.drop_table("content_items")
