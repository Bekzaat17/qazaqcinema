"""Сетка контент-плана и разрез длинного текста — чистые функции, без БД и Telegram."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.channel.content.item import MESSAGE_LIMIT, ContentItem
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.plan import SLOTS, closes_at, slot_for, slot_key
from app.domain.channel.content.render.base import footer, frame, header
from app.domain.channel.content.split import split_text
from app.domain.channel.content.topics import CHANNEL_HASHTAG, TOPICS


def _almaty(year: int, month: int, day: int, hour: int) -> datetime:
    """Местное время Алматы (UTC+5) → UTC, как приходит в джоб."""
    return datetime(year, month, day, hour - 5, 0, tzinfo=UTC)


# ── Сетка ────────────────────────────────────────────────────────────────────


def test_sunday_19_is_abai_with_saying_fallback() -> None:
    """Воскресенье 19:00 — қара сөз без повторов; кончатся → нақыл сөз. Это и есть цепочка."""
    slot = slot_for(_almaty(2026, 9, 13, 19))  # воскресенье
    assert slot is not None and slot.name == "abai"
    first, second = slot.sources
    assert first.kind is ContentKind.LONGREAD and first.topic == "abai" and not first.repeat
    assert second.kind is ContentKind.SAYING and second.repeat


def test_hours_are_local_not_utc() -> None:
    """Контейнеры в UTC: 14:00 UTC — это 19:00 по Алматы, слот должен найтись именно тогда."""
    assert slot_for(datetime(2026, 9, 13, 14, 0, tzinfo=UTC)) is not None
    assert slot_for(datetime(2026, 9, 13, 19, 0, tzinfo=UTC)) is None  # это уже полночь


def test_no_slot_collides_with_daily_movie_post() -> None:
    """10:00 занят фильмом дня — два поста подряд склеиваются в ленте."""
    assert all(slot.hour != 10 for slot in SLOTS)
    assert len({slot.name for slot in SLOTS}) == len(SLOTS)  # имена — часть slot_key


def test_quiz_slot_closes_same_day_and_key_is_local_date() -> None:
    now = _almaty(2026, 9, 14, 12)  # понедельник
    slot = slot_for(now)
    assert slot is not None and slot.name == "quiz-mon"
    assert slot_key(slot, now) == "2026-09-14:quiz-mon"
    closes = closes_at(slot, now)
    assert closes is not None and (closes.hour, closes.day) == (21, 14)
    assert closes_at(SLOTS[1], now) is None  # не квиз — не закрывается


def test_every_topic_has_a_clickable_hashtag() -> None:
    for topic in TOPICS.values():
        assert topic.hashtag.startswith("#") and " " not in topic.hashtag


# ── Разрез текста ────────────────────────────────────────────────────────────


def test_short_text_is_one_chunk_and_empty_is_none() -> None:
    assert split_text("Сөз.", 100) == ["Сөз."]
    assert split_text("   ", 100) == []


def test_split_prefers_paragraph_boundaries() -> None:
    a, b, c = "А" * 40 + ".", "Б" * 40 + ".", "В" * 40 + "."
    chunks = split_text(f"{a}\n\n{b}\n\n{c}", limit=90)
    assert chunks == [f"{a}\n\n{b}", c]


def test_long_paragraph_is_split_at_sentence_end_never_mid_sentence() -> None:
    sentences = [f"Сөйлем {i} бітті." for i in range(30)]
    chunks = split_text(" ".join(sentences), limit=60)
    assert all(len(chunk) <= 60 for chunk in chunks)
    assert all(chunk.endswith(".") for chunk in chunks)
    assert " ".join(chunks) == " ".join(sentences)


def test_qara_soz_size_fits_telegram() -> None:
    text = "\n\n".join("Абзац " * 200 + "соңы." for _ in range(6))  # ~7 000 символов
    chunks = split_text(text, MESSAGE_LIMIT)
    assert len(chunks) == 2
    assert all(len(chunk) <= MESSAGE_LIMIT for chunk in chunks)


# ── Каркас поста ─────────────────────────────────────────────────────────────


def _item(**overrides: object) -> ContentItem:
    base: dict[str, object] = {
        "slug": "x", "kind": ContentKind.SAYING, "topic": "nakyl",
        "title_kk": "Тақырып", "body_kk": "Мәтін", "source": "Абай <3",
    }
    return ContentItem(**(base | overrides))  # type: ignore[arg-type]


def test_frame_has_rubric_header_hashtags_and_escaped_source() -> None:
    text = frame(_item(), "Тело", 4096)
    assert text.startswith("💬 <b>Нақыл сөз</b>")
    assert "<i>Абай &lt;3</i>" in text
    assert text.endswith(f"#НақылСөз {CHANNEL_HASHTAG}")


def test_frame_clips_body_not_footer() -> None:
    """Хэштеги — навигация, они должны выжить даже когда тело не влезает."""
    text = frame(_item(), "Ә" * 5000, 1024)
    assert len(text) <= 1024
    assert text.endswith(f"#НақылСөз {CHANNEL_HASHTAG}")
    assert "…" in text


def test_image_credit_only_when_there_is_an_image() -> None:
    assert "📷" not in footer(_item(image_credit="Commons"))
    assert "📷 Commons" in footer(_item(image_path="channel/x.jpg", image_credit="Commons"))
    assert header(_item(topic="unknown")) == "<b>Тақырып</b>"
