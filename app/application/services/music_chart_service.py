"""Еженедельный хит-парад в публичный канал — витрина того, что каталог живой.

Пост несёт и «что ищут, но нет»: это прямой призыв к подписчикам, у которых песня
есть, прислать её боту. Так канал работает на рост каталога, а не только показывает его.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from app.application.ports.channel import ChannelPost, ChannelPublisher
from app.application.ports.music import MusicChartLog, MusicRequestRepository, TrackRepository
from app.domain.catalog.daily import TZ
from app.domain.music.chart import CHART_SIZE, WANTED_SIZE, WeeklyChart, has_content, render_chart
from app.domain.subscription.weekly import week_start


class MusicChartService:
    def __init__(
        self,
        tracks: TrackRepository,
        requests: MusicRequestRepository,
        log: MusicChartLog,
        publisher: ChannelPublisher,
        bot_username: str,
    ) -> None:
        self._tracks = tracks
        self._requests = requests
        self._log = log
        self._publisher = publisher
        self._bot = bot_username.lstrip("@")

    async def build(self, now: datetime) -> WeeklyChart:
        week = week_start(now)
        since = datetime.combine(week, time(), tzinfo=TZ).astimezone(UTC)
        # Окно — с начала местной недели до момента поста, плюс хвост прошлой: в пятницу
        # вечером своя неделя ещё неполная, и топ из четырёх дней шумит.
        since -= timedelta(days=3)
        top = await self._tracks.top_played(since, now, CHART_SIZE)
        added = await self._tracks.count_added(since, now)
        wanted = await self._requests.list_open(WANTED_SIZE)
        return WeeklyChart(week, tuple(top), added, tuple(r.query for r in wanted))

    async def publish_weekly(self, now: datetime) -> bool:
        week = week_start(now)
        if await self._log.posted(week):
            return False
        chart = await self.build(now)
        if not has_content(chart):
            return False
        message_id = await self._publisher.publish(ChannelPost(
            text=render_chart(chart),
            button_text="🎧 Тыңдау",
            button_url=f"https://t.me/{self._bot}?startapp=music",
        ))
        if message_id is None:
            return False
        await self._log.record(week, message_id, now)
        return True
