from __future__ import annotations

from datetime import datetime

import fakeredis.aioredis
from app.application.services.quest_channel_service import QuestChannelService
from app.domain.quest.game import RankEntry, RankingPeriod
from app.infrastructure.cache.quest import RedisQuestRankingCache

from tests.test_quest_rules import NOW


class _Rankings:
    async def leaders(
        self,
        period: RankingPeriod,
        now: datetime,
        *,
        fresh: bool = False,
    ) -> tuple[RankEntry, ...]:
        return (RankEntry(42, 1, 100),)


class _Store:
    def __init__(self) -> None:
        self.records: dict[str, int | None] = {}

    async def message_id(self, key: str) -> int | None:
        return self.records.get(key)

    async def reserve(self, key: str) -> bool:
        if key in self.records:
            return False
        self.records[key] = None
        return True

    async def delivered(self, key: str, message_id: int) -> None:
        self.records[key] = message_id


class _Publisher:
    channel_id = -100123

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.updated: list[int] = []
        self.fail = False

    async def send(self, text: str) -> int | None:
        self.sent.append(text)
        return None if self.fail else len(self.sent)

    async def update(self, message_id: int, text: str) -> None:
        self.updated.append(message_id)


async def test_hourly_refresh_edits_one_post_and_weekly_final_is_sent_once() -> None:
    publisher, store = _Publisher(), _Store()
    service = QuestChannelService(_Rankings(), store, publisher)  # type: ignore[arg-type]
    await service.publish(NOW)
    await service.publish(NOW)
    assert len(publisher.sent) == 2
    assert "Апта жеңімпаздары" in publisher.sent[0]
    assert "Апталық рейтинг" in publisher.sent[1]
    assert publisher.updated == [2]


async def test_uncertain_delivery_does_not_spam_after_restart() -> None:
    publisher, store = _Publisher(), _Store()
    publisher.fail = True
    service = QuestChannelService(_Rankings(), store, publisher)  # type: ignore[arg-type]
    await service.publish(NOW)
    restarted = QuestChannelService(_Rankings(), store, publisher)  # type: ignore[arg-type]
    await restarted.publish(NOW)
    assert len(publisher.sent) == 2
    assert not publisher.updated


async def test_no_channel_means_no_external_effects() -> None:
    publisher = _Publisher()
    publisher.channel_id = 0
    await QuestChannelService(_Rankings(), _Store(), publisher).publish(NOW)  # type: ignore[arg-type]
    assert not publisher.sent


async def test_rank_cache_preserves_entries_and_corruption_becomes_a_miss() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache = RedisQuestRankingCache(redis)
    entries = (RankEntry(42, 1, 100),)
    assert await cache.get("week") is None
    await cache.set("week", entries, 300)
    assert await cache.get("week") == entries
    assert 0 < await redis.ttl("quest:ranking:week") <= 300
    await redis.set("quest:ranking:week", "broken")
    assert await cache.get("week") is None
    await redis.aclose()
