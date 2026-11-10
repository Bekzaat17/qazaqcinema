from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.application.ports.quest import QuestChannelPublisher, QuestChannelStore
from app.application.services.quest_ranking_service import QuestRankingService
from app.domain.quest.channel import render_ranking
from app.domain.quest.game import RankingPeriod
from app.domain.subscription.weekly import week_start

logger = logging.getLogger(__name__)


class QuestChannelService:
    def __init__(
        self,
        rankings: QuestRankingService,
        store: QuestChannelStore,
        publisher: QuestChannelPublisher,
    ) -> None:
        self._rankings = rankings
        self._store = store
        self._publisher = publisher

    async def publish(self, now: datetime) -> None:
        if not self._publisher.channel_id:
            return
        for final, moment in ((True, now - timedelta(days=7)), (False, now)):
            week = week_start(moment)
            entries = await self._rankings.leaders(RankingPeriod.WEEK, moment, fresh=True)
            if not entries:
                continue
            key = f"{self._publisher.channel_id}:{week}:{'final' if final else 'live'}"
            message_id = await self._store.message_id(key)
            text = render_ranking(entries, week, final=final)
            if message_id is not None:
                if not final:
                    await self._publisher.update(message_id, text)
                continue
            if not await self._store.reserve(key):
                logger.warning("Публикация QazaqQuest %s требует проверки доставки", key)
                continue
            sent = await self._publisher.send(text)
            if sent is not None:
                await self._store.delivered(key, sent)
            else:
                logger.error("Не удалось подтвердить публикацию QazaqQuest %s", key)
