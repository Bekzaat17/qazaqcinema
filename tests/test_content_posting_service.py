"""Публикация контента по слоту: выбор по цепочке источников, журнал, идемпотентность.
Без БД и Telegram — фейки портов."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.application.ports.channel import ChannelPost
from app.application.ports.content import PostLogEntry
from app.application.services.content_posting_service import ContentPostingService
from app.domain.channel.content.item import ContentItem
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.plan import Source
from app.domain.channel.content.render.base import CallbackButton, RenderedPost

SUNDAY_19 = datetime(2026, 9, 13, 14, 0, tzinfo=UTC)  # 19:00 Алматы
MONDAY_12 = datetime(2026, 9, 14, 7, 0, tzinfo=UTC)


def _item(item_id: int, kind: ContentKind, topic: str = "abai") -> ContentItem:
    return ContentItem(
        id=item_id, slug=f"s{item_id}", kind=kind, topic=topic,
        title_kk="T", body_kk="B", image_path="channel/x.jpg",
    )


class FakeItems:
    def __init__(self, pool: dict[tuple[ContentKind, str | None], list[ContentItem]]) -> None:
        self.pool = pool
        self.marked: list[int] = []
        self.asked: list[Source] = []

    async def next_for(self, source: Source, today: date) -> ContentItem | None:
        self.asked.append(source)
        items = self.pool.get((source.kind, source.topic), [])
        return items[0] if items else None

    async def mark_posted(self, item_id: int, at: datetime) -> None:
        self.marked.append(item_id)


class FakeLog:
    def __init__(self, existing: set[str] | None = None) -> None:
        self.entries: list[PostLogEntry] = []
        self._existing = existing or set()

    async def add(self, entry: PostLogEntry) -> PostLogEntry | None:
        self.entries.append(entry)
        return entry

    async def exists(self, slot_key: str) -> bool:
        return slot_key in self._existing


class FakePublisher:
    def __init__(self, ok: bool = True) -> None:
        self.posts: list[ChannelPost] = []
        self._ok = ok

    async def publish(self, post: ChannelPost) -> int | None:
        self.posts.append(post)
        return 100 + len(self.posts) if self._ok else None

    async def remove_buttons(self, message_id: int) -> bool:
        return True


class StubRenderer:
    def __init__(self, tail: int = 0, buttons: int = 0) -> None:
        self._tail, self._buttons = tail, buttons

    def render(self, item: ContentItem) -> RenderedPost:
        return RenderedPost(
            head=f"head:{item.slug}",
            tail=tuple(f"tail{i}" for i in range(self._tail)),
            buttons=tuple(CallbackButton(str(i), f"q:{i}") for i in range(self._buttons)),
        )


def _service(items: FakeItems, log: FakeLog, publisher: FakePublisher, **renderers: object):
    rend = {ContentKind(k): v for k, v in renderers.items()} or {
        kind: StubRenderer() for kind in ContentKind
    }
    return ContentPostingService(items, log, publisher, rend)  # type: ignore[arg-type]


async def test_sunday_posts_abai_and_logs_slot() -> None:
    items = FakeItems({(ContentKind.LONGREAD, "abai"): [_item(1, ContentKind.LONGREAD)]})
    log, publisher = FakeLog(), FakePublisher()

    assert await _service(items, log, publisher).post_slot(SUNDAY_19) is True

    assert publisher.posts[0].text == "head:s1"
    assert publisher.posts[0].photo_path == "channel/x.jpg"
    entry = log.entries[0]
    assert (entry.slot_key, entry.item_id, entry.channel_message_id) == ("2026-09-13:abai", 1, 101)
    assert entry.quiz_closes_at is None
    assert items.marked == [1]


async def test_falls_back_to_saying_when_abai_pool_is_exhausted() -> None:
    """Цепочка источников: қара сөз кончились → воскресенье занимает нақыл сөз."""
    items = FakeItems({(ContentKind.SAYING, None): [_item(7, ContentKind.SAYING, "nakyl")]})
    log, publisher = FakeLog(), FakePublisher()

    assert await _service(items, log, publisher).post_slot(SUNDAY_19) is True

    assert [s.kind for s in items.asked] == [ContentKind.LONGREAD, ContentKind.SAYING]
    assert log.entries[0].kind is ContentKind.SAYING


async def test_empty_pool_posts_nothing() -> None:
    items, log, publisher = FakeItems({}), FakeLog(), FakePublisher()
    assert await _service(items, log, publisher).post_slot(SUNDAY_19) is False
    assert publisher.posts == [] and log.entries == [] and items.marked == []


async def test_no_slot_at_this_hour_is_a_noop() -> None:
    items = FakeItems({(ContentKind.LONGREAD, "abai"): [_item(1, ContentKind.LONGREAD)]})
    publisher = FakePublisher()
    off_hour = datetime(2026, 9, 13, 3, 0, tzinfo=UTC)
    assert await _service(items, FakeLog(), publisher).post_slot(off_hour) is False
    assert publisher.posts == []


async def test_already_logged_slot_is_not_posted_twice() -> None:
    """Рестарт бота внутри misfire-окна: слот уже в журнале — второго поста в канале нет."""
    items = FakeItems({(ContentKind.LONGREAD, "abai"): [_item(1, ContentKind.LONGREAD)]})
    publisher = FakePublisher()
    log = FakeLog(existing={"2026-09-13:abai"})
    assert await _service(items, log, publisher).post_slot(SUNDAY_19) is False
    assert publisher.posts == [] and items.marked == []


async def test_long_text_goes_as_consecutive_messages_photo_only_on_first() -> None:
    items = FakeItems({(ContentKind.LONGREAD, "abai"): [_item(1, ContentKind.LONGREAD)]})
    publisher = FakePublisher()
    service = _service(items, FakeLog(), publisher, longread=StubRenderer(tail=2))

    assert await service.post_slot(SUNDAY_19) is True
    assert [p.text for p in publisher.posts] == ["head:s1", "tail0", "tail1"]
    assert publisher.posts[0].photo_path and publisher.posts[1].photo_path is None


async def test_quiz_slot_carries_buttons_and_closing_time() -> None:
    quiz = _item(3, ContentKind.QUIZ_CHOICE, "maqal")
    items = FakeItems({(ContentKind.QUIZ_CHOICE, None): [quiz]})
    log, publisher = FakeLog(), FakePublisher()
    service = _service(items, log, publisher, quiz_choice=StubRenderer(buttons=4))

    assert await service.post_slot(MONDAY_12) is True
    assert [b.data for b in publisher.posts[0].choices] == ["q:0", "q:1", "q:2", "q:3"]
    closes = log.entries[0].quiz_closes_at
    assert closes is not None and closes.astimezone(UTC).hour == 16  # 21:00 Алматы


async def test_publisher_failure_leaves_no_trace() -> None:
    """Канал не настроен/лёг → ничего не отмечаем: слот повторит попытку следующим часом
    только если это ещё его час; журнал и ротация остаются чистыми."""
    items = FakeItems({(ContentKind.LONGREAD, "abai"): [_item(1, ContentKind.LONGREAD)]})
    log = FakeLog()
    assert await _service(items, log, FakePublisher(ok=False)).post_slot(SUNDAY_19) is False
    assert log.entries == [] and items.marked == []


async def test_missing_renderer_is_skipped_not_crashed() -> None:
    items = FakeItems({(ContentKind.LONGREAD, "abai"): [_item(1, ContentKind.LONGREAD)]})
    publisher = FakePublisher()
    service = ContentPostingService(items, FakeLog(), publisher, {})  # type: ignore[arg-type]
    assert await service.post_slot(SUNDAY_19) is False
    assert publisher.posts == []
