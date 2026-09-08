"""Публикация контента канала: слот → элемент → рендер → пост → журнал.

Два входа, оба из планировщика: `post_slot` — недельная сетка (ежечасный джоб), а
`post_holiday` — поздравление с праздником (джоб на каждое время из данных календаря).
В праздник сетка молчит: два поста об одном дне обесценивают рубрику. Сервис не знает ни про
Telegram (порт `ChannelPublisher`), ни про SQL (порт `ContentRepository` с правилом
ротации внутри), ни про диск (картинка — относительный путь, корень знает адаптер).

Идемпотентность — двумя слоями: до публикации `exists(slot_key)` (обычный случай:
рестарт бота внутри misfire-окна), после — UNIQUE `slot_key` в журнале. Между двумя
процессами гонка теоретически возможна, но планировщик поднимает ТОЛЬКО процесс бота
(см. `scheduler.py`), поэтому распределённого лока здесь нет — он лечил бы то, чего
по топологии не бывает.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime

from app.application.ports.channel import ChannelPost, ChannelPublisher
from app.application.ports.content import ContentRepository, PostLogEntry, PostLogRepository
from app.domain.catalog.daily import TZ
from app.domain.channel.content.item import ContentItem
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.plan import Slot, closes_at, slot_for, slot_key
from app.domain.channel.content.render.base import ContentRenderer
from app.domain.channel.holidays import holiday_for, holiday_slot_key, holiday_today

logger = logging.getLogger(__name__)


class ContentPostingService:
    def __init__(
        self,
        items: ContentRepository,
        log: PostLogRepository,
        publisher: ChannelPublisher,
        renderers: Mapping[ContentKind, ContentRenderer],
    ) -> None:
        self._items = items
        self._log = log
        self._publisher = publisher
        self._renderers = renderers

    async def post_slot(self, now: datetime) -> bool:
        """Опубликовать пост слота, если его час наступил. `True` — пост ушёл.

        `False` во всех остальных случаях — не ошибка: нет слота в этот час, слот уже
        опубликован, пул пуст, канал не настроен. Джоб логирует только успех.
        """
        slot = slot_for(now)
        if slot is None:
            return False
        # Праздник главнее сетки: иначе за сутки выходит поздравление, фильм дня в 10:00
        # и ещё рубрика вечером. Фильм дня остаётся — это крючок продукта.
        if (holiday := holiday_today(now)) is not None:
            logger.info("Слот %s пропущен: сегодня %s", slot.name, holiday.title_kk)
            return False
        key = slot_key(slot, now)
        if await self._log.exists(key):
            return False

        item = await self._pick(slot, now)
        if item is None:
            logger.info("Слот %s: пул пуст по всем источникам — пост не публикуем", key)
            return False
        renderer = self._renderers.get(item.kind)
        if renderer is None:
            # Форма без рендерера: залили YAML раньше кода. Не падаем — слот молчит,
            # а в логе видно, чего не хватает.
            logger.warning("Слот %s: нет рендерера для формы %s", key, item.kind)
            return False

        post = renderer.render(item)
        first_id = await self._publisher.publish(
            ChannelPost(text=post.head, photo_path=item.image_path, choices=post.buttons)
        )
        if first_id is None:
            return False
        for text in post.tail:
            # Хвост қара сөз — отдельными сообщениями подряд. Сбой хвоста не откатывает
            # голову (её уже видят), но и не мешает записать журнал: пост состоялся.
            if await self._publisher.publish(ChannelPost(text=text)) is None:
                logger.warning("Слот %s: часть текста не ушла в канал", key)
                break

        assert item.id is not None  # элемент из БД
        await self._log.add(
            PostLogEntry(
                slot_key=key,
                item_id=item.id,
                kind=item.kind,
                channel_message_id=first_id,
                posted_at=now,
                quiz_closes_at=closes_at(slot, now),
            )
        )
        await self._items.mark_posted(item.id, now)
        return True

    async def post_holiday(self, now: datetime) -> bool:
        """Поздравить с праздником, если его час наступил. `True` — пост ушёл.

        Элемент берём по slug праздника (`content/holidays.yaml`), а не ротацией: 21
        наурыз нужен ровно наурызовский текст. Нет элемента в пуле (залили код раньше
        контента) или у лунного праздника не заполнен год — канал молчит, а в логе
        видно, чего не хватает.
        """
        holiday = holiday_for(now)
        if holiday is None:
            return False
        key = holiday_slot_key(holiday, now)
        if await self._log.exists(key):
            return False

        item = await self._items.by_slug(holiday.slug)
        if item is None:
            logger.warning("Праздник %s: нет элемента «%s» в пуле", holiday.title_kk, holiday.slug)
            return False
        renderer = self._renderers.get(item.kind)
        if renderer is None:
            logger.warning("Праздник %s: нет рендерера для формы %s", holiday.title_kk, item.kind)
            return False

        post = renderer.render(item)
        # Без кнопок: пост с inline-клавиатурой не попадает в группу обсуждений, а
        # комментарии под поздравлением — весь его смысл.
        message_id = await self._publisher.publish(
            ChannelPost(text=post.head, photo_path=item.image_path)
        )
        if message_id is None:
            return False

        assert item.id is not None  # элемент из БД
        await self._log.add(
            PostLogEntry(
                slot_key=key,
                item_id=item.id,
                kind=item.kind,
                channel_message_id=message_id,
                posted_at=now,
            )
        )
        await self._items.mark_posted(item.id, now)
        return True

    async def _pick(self, slot: Slot, now: datetime) -> ContentItem | None:
        """Первый источник цепочки, у которого есть что постить (фолбэк — см. `plan`)."""
        today = now.astimezone(TZ).date()
        for source in slot.sources:
            item = await self._items.next_for(source, today)
            if item is not None:
                return item
        return None
