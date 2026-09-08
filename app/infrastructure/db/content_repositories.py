"""Pg-реализации портов контента канала (`application/ports/content`).

Отдельный модуль от пакета `repositories/` — та же роль: мапят ORM ↔ домен,
коммитят сами (один вызов = одна транзакция).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date, datetime

from sqlalchemy import ColumnElement, case, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.content import PostLogEntry, QuizStatsRow
from app.domain.channel.content.item import ContentItem
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.plan import Source
from app.infrastructure.db.content_codec import payload_from_json, payload_to_json
from app.infrastructure.db.models import ChannelPostLogModel, ContentItemModel, QuizAnswerModel
from app.infrastructure.db.sql import rowcount

logger = logging.getLogger(__name__)


def _item_to_domain(model: ContentItemModel) -> ContentItem:
    kind = ContentKind(model.kind)
    return ContentItem(
        id=model.id,
        slug=model.slug,
        kind=kind,
        topic=model.topic,
        title_kk=model.title_kk,
        body_kk=model.body_kk,
        source=model.source,
        image_path=model.image_path,
        image_credit=model.image_credit,
        payload=payload_from_json(kind, model.payload),
        scheduled_for=model.scheduled_for,
        last_posted_at=model.last_posted_at,
        post_count=model.post_count,
        is_active=model.is_active,
        created_at=model.created_at,
    )


class PgContentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_for(self, source: Source, today: date) -> ContentItem | None:
        """Правило ротации — см. докстринг порта. Один запрос: фильтр + порядок + LIMIT 1.

        Порядок: пин на сегодня → никогда не постившиеся → самые давние → id.
        `nulls_first` у `last_posted_at ASC` и делает «никогда» первыми.
        """
        conditions: list[ColumnElement[bool]] = [
            ContentItemModel.is_active.is_(True),
            ContentItemModel.kind == source.kind.value,
        ]
        if source.topic is not None:
            conditions.append(ContentItemModel.topic == source.topic)
        if not source.repeat:
            conditions.append(ContentItemModel.last_posted_at.is_(None))
        # CASE, а не голое сравнение: у незакреплённых `scheduled_for IS NULL`, и сравнение
        # даёт NULL, который в сортировке ведёт себя не как FALSE (DESC ставит NULL первым).
        pinned_today = case((ContentItemModel.scheduled_for == today, 1), else_=0).desc()
        stmt = (
            select(ContentItemModel)
            .where(*conditions)
            .order_by(
                pinned_today,
                ContentItemModel.last_posted_at.asc().nulls_first(),
                ContentItemModel.id,
            )
            .limit(1)
        )
        model = await self._session.scalar(stmt)
        return _item_to_domain(model) if model else None

    async def mark_posted(self, item_id: int, at: datetime) -> None:
        await self._session.execute(
            update(ContentItemModel)
            .where(ContentItemModel.id == item_id)
            .values(last_posted_at=at, post_count=ContentItemModel.post_count + 1)
        )
        await self._session.commit()

    async def get(self, item_id: int) -> ContentItem | None:
        model = await self._session.get(ContentItemModel, item_id)
        return _item_to_domain(model) if model else None

    async def upsert_many(self, items: list[ContentItem]) -> int:
        """INSERT … ON CONFLICT (slug) DO UPDATE содержимого; ротация не трогается."""
        if not items:
            return 0
        rows = [
            {
                "slug": item.slug,
                "kind": item.kind.value,
                "topic": item.topic,
                "title_kk": item.title_kk,
                "body_kk": item.body_kk,
                "source": item.source,
                "image_path": item.image_path,
                "image_credit": item.image_credit,
                "payload": payload_to_json(item.payload),
                "scheduled_for": item.scheduled_for,
                "is_active": item.is_active,
            }
            for item in items
        ]
        stmt = pg_insert(ContentItemModel).values(rows)
        content_keys = [key for key in rows[0] if key != "slug"]
        stmt = stmt.on_conflict_do_update(
            index_elements=["slug"],
            set_={key: stmt.excluded[key] for key in content_keys},
        )
        await self._session.execute(stmt)
        await self._session.commit()
        return len(rows)

    async def count_by_kind(self) -> dict[ContentKind, int]:
        stmt = (
            select(ContentItemModel.kind, func.count())
            .where(ContentItemModel.is_active.is_(True))
            .group_by(ContentItemModel.kind)
        )
        rows = await self._session.execute(stmt)
        return {ContentKind(kind): int(count) for kind, count in rows}


def _log_to_domain(model: ChannelPostLogModel) -> PostLogEntry:
    return PostLogEntry(
        id=model.id,
        slot_key=model.slot_key,
        item_id=model.item_id,
        kind=ContentKind(model.kind),
        channel_message_id=model.channel_message_id,
        group_message_id=model.group_message_id,
        posted_at=model.posted_at,
        quiz_closes_at=model.quiz_closes_at,
        result_posted_at=model.result_posted_at,
    )


class PgPostLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: PostLogEntry) -> PostLogEntry | None:
        """`ON CONFLICT (slot_key) DO NOTHING` — дубль слота отдаёт None, не исключение."""
        stmt = (
            pg_insert(ChannelPostLogModel)
            .values(
                slot_key=entry.slot_key,
                item_id=entry.item_id,
                kind=entry.kind.value,
                channel_message_id=entry.channel_message_id,
                group_message_id=entry.group_message_id,
                posted_at=entry.posted_at,
                quiz_closes_at=entry.quiz_closes_at,
                result_posted_at=entry.result_posted_at,
            )
            .on_conflict_do_nothing(index_elements=["slot_key"])
            .returning(ChannelPostLogModel.id)
        )
        new_id = await self._session.scalar(stmt)
        await self._session.commit()
        if new_id is None:
            logger.warning("Слот %s уже в журнале — запись пропущена", entry.slot_key)
            return None
        return replace(entry, id=int(new_id))

    async def exists(self, slot_key: str) -> bool:
        stmt = select(ChannelPostLogModel.id).where(ChannelPostLogModel.slot_key == slot_key)
        return await self._session.scalar(stmt) is not None

    async def get_by_channel_message(self, channel_message_id: int) -> PostLogEntry | None:
        stmt = select(ChannelPostLogModel).where(
            ChannelPostLogModel.channel_message_id == channel_message_id
        )
        model = await self._session.scalar(stmt)
        return _log_to_domain(model) if model else None

    async def get_by_group_message(self, group_message_id: int) -> PostLogEntry | None:
        stmt = select(ChannelPostLogModel).where(
            ChannelPostLogModel.group_message_id == group_message_id
        )
        model = await self._session.scalar(stmt)
        return _log_to_domain(model) if model else None

    async def bind_group_message(self, channel_message_id: int, group_message_id: int) -> bool:
        bound = await rowcount(
            self._session,
            update(ChannelPostLogModel)
            .where(ChannelPostLogModel.channel_message_id == channel_message_id)
            .values(group_message_id=group_message_id),
        )
        await self._session.commit()
        return bool(bound)

    async def list_due_results(self, now: datetime) -> list[PostLogEntry]:
        stmt = (
            select(ChannelPostLogModel)
            .where(
                ChannelPostLogModel.quiz_closes_at.is_not(None),
                ChannelPostLogModel.quiz_closes_at <= now,
                ChannelPostLogModel.result_posted_at.is_(None),
            )
            .order_by(ChannelPostLogModel.quiz_closes_at)
        )
        return [_log_to_domain(m) for m in await self._session.scalars(stmt)]

    async def mark_result_posted(self, post_id: int, at: datetime) -> None:
        await self._session.execute(
            update(ChannelPostLogModel)
            .where(ChannelPostLogModel.id == post_id)
            .values(result_posted_at=at)
        )
        await self._session.commit()


class PgQuizAnswerRepository:
    """Ответы на квиз. Первый ответ — единственный: `ON CONFLICT (post_id, user_id) DO NOTHING`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_first(
        self,
        post_id: int,
        user_id: int,
        first_name: str,
        text: str,
        is_correct: bool,
        at: datetime,
    ) -> bool:
        stmt = (
            pg_insert(QuizAnswerModel)
            .values(
                post_id=post_id,
                user_id=user_id,
                first_name=first_name,
                text=text,
                is_correct=is_correct,
                answered_at=at,
            )
            .on_conflict_do_nothing(constraint="uq_quiz_answers_post_user")
            .returning(QuizAnswerModel.id)
        )
        inserted = await self._session.scalar(stmt)
        await self._session.commit()
        return inserted is not None

    async def stats(self, post_id: int, first_n: int) -> QuizStatsRow:
        totals = await self._session.execute(
            select(
                func.count(),
                func.count().filter(QuizAnswerModel.is_correct.is_(True)),
            ).where(QuizAnswerModel.post_id == post_id)
        )
        total, correct = totals.one()
        first = await self._session.scalars(
            select(QuizAnswerModel.first_name)
            .where(QuizAnswerModel.post_id == post_id, QuizAnswerModel.is_correct.is_(True))
            .order_by(QuizAnswerModel.answered_at, QuizAnswerModel.id)
            .limit(first_n)
        )
        return QuizStatsRow(int(total), int(correct), tuple(first))
