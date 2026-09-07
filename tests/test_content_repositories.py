"""Интеграционные тесты пула контента и журнала публикаций (нужен Postgres)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.application.ports.content import PostLogEntry
from app.domain.channel.content.item import ContentItem, QuizChoice, Term, TermList
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.plan import Source
from app.infrastructure.db.content_repositories import PgContentRepository, PgPostLogRepository
from sqlalchemy.ext.asyncio import AsyncSession

NOW = datetime(2026, 9, 13, 14, 0, tzinfo=UTC)
TODAY = date(2026, 9, 13)


def _abai(n: int, **overrides: object) -> ContentItem:
    base: dict[str, object] = {
        "slug": f"abai-{n:02d}", "kind": ContentKind.LONGREAD, "topic": "abai",
        "title_kk": f"{n}-ші қара сөз", "body_kk": "мәтін", "source": "Абай",
    }
    return ContentItem(**(base | overrides))  # type: ignore[arg-type]


async def test_upsert_is_idempotent_and_keeps_rotation_state(session: AsyncSession) -> None:
    repo = PgContentRepository(session)
    assert await repo.upsert_many([_abai(1), _abai(2)]) == 2
    first = await repo.next_for(Source(ContentKind.LONGREAD, "abai"), TODAY)
    assert first is not None and first.id is not None
    await repo.mark_posted(first.id, NOW)

    # Повторная заливка с правкой текста: элементов не стало больше, история не сброшена.
    await repo.upsert_many([_abai(1, body_kk="исправленный"), _abai(2)])
    assert await repo.count_by_kind() == {ContentKind.LONGREAD: 2}
    again = await repo.get(first.id)
    assert again is not None and again.post_count == 1 and again.body_kk == "исправленный"


async def test_rotation_never_posted_first_then_oldest(session: AsyncSession) -> None:
    repo = PgContentRepository(session)
    await repo.upsert_many([_abai(1), _abai(2), _abai(3)])
    src = Source(ContentKind.LONGREAD, "abai")

    a = await repo.next_for(src, TODAY)
    assert a is not None and a.slug == "abai-01"  # tie-break по id
    await repo.mark_posted(a.id or 0, NOW - timedelta(days=14))
    b = await repo.next_for(src, TODAY)
    assert b is not None and b.slug == "abai-02"  # никогда не постившийся раньше давнего
    await repo.mark_posted(b.id or 0, NOW - timedelta(days=7))
    c = await repo.next_for(src, TODAY)
    assert c is not None and c.slug == "abai-03"
    await repo.mark_posted(c.id or 0, NOW)

    # Все постились: repeat=True → самый давний (abai-01); repeat=False → пул исчерпан.
    lru = await repo.next_for(src, TODAY)
    assert lru is not None and lru.slug == "abai-01"
    assert await repo.next_for(Source(ContentKind.LONGREAD, "abai", repeat=False), TODAY) is None


async def test_scheduled_pin_beats_rotation_only_on_its_day(session: AsyncSession) -> None:
    repo = PgContentRepository(session)
    await repo.upsert_many([_abai(1), _abai(2, scheduled_for=TODAY)])
    src = Source(ContentKind.LONGREAD, "abai")
    pinned = await repo.next_for(src, TODAY)
    assert pinned is not None and pinned.slug == "abai-02"
    other_day = await repo.next_for(src, TODAY + timedelta(days=1))
    assert other_day is not None and other_day.slug == "abai-01"


async def test_filters_by_kind_topic_and_active(session: AsyncSession) -> None:
    repo = PgContentRepository(session)
    quiz = ContentItem(
        slug="q-1", kind=ContentKind.QUIZ_CHOICE, topic="maqal", title_kk="", body_kk="",
        payload=QuizChoice("Еңбек етсең ерінбей…", ("тояды қарның тіленбей", "жоқ"), 0),
    )
    terms = ContentItem(
        slug="t-1", kind=ContentKind.TERM_LIST, topic="zhylqy", title_kk="Жылқы жасы",
        body_kk="", payload=TermList((Term("құлын", "бір жасқа дейін"),), note="…"),
    )
    await repo.upsert_many([_abai(1), _abai(2, topic="nakyl", is_active=False), quiz, terms])

    assert await repo.next_for(Source(ContentKind.LONGREAD, "nakyl"), TODAY) is None  # неактивен
    got_quiz = await repo.next_for(Source(ContentKind.QUIZ_CHOICE), TODAY)
    assert got_quiz is not None and isinstance(got_quiz.payload, QuizChoice)
    assert got_quiz.payload.options[0] == "тояды қарның тіленбей"
    got_terms = await repo.next_for(Source(ContentKind.TERM_LIST), TODAY)
    assert got_terms is not None and isinstance(got_terms.payload, TermList)
    assert got_terms.payload.items[0].term == "құлын"


async def test_post_log_slot_key_is_unique(session: AsyncSession) -> None:
    items = PgContentRepository(session)
    await items.upsert_many([_abai(1)])
    item = await items.next_for(Source(ContentKind.LONGREAD, "abai"), TODAY)
    assert item is not None and item.id is not None
    log = PgPostLogRepository(session)
    entry = PostLogEntry(
        slot_key="2026-09-13:abai", item_id=item.id, kind=ContentKind.LONGREAD,
        channel_message_id=555, posted_at=NOW,
    )

    assert not await log.exists("2026-09-13:abai")
    saved = await log.add(entry)
    assert saved is not None and saved.id is not None
    assert await log.exists("2026-09-13:abai")
    assert await log.add(entry) is None  # дубль слота — тихо

    found = await log.get_by_channel_message(555)
    assert found is not None and found.slot_key == "2026-09-13:abai"
    assert await log.get_by_channel_message(556) is None
