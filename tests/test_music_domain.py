"""Правила музыки без БД: разбор названий, ссылки, подпись прослушивания, хит-парад."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.domain.music.chart import ChartEntry, WeeklyChart, has_content, render_chart
from app.domain.music.links import MusicLink, parse_music_link
from app.domain.music.playlist import DEFAULT_TITLE, TITLE_MAX, new_share_code, playlist_title
from app.domain.music.stream import stream_expiry, stream_signature, verify_stream
from app.domain.music.track import (
    UNKNOWN_PERFORMER,
    AudioUpload,
    is_music,
    search_key,
    track_name,
)

_NOW = datetime(2026, 11, 27, 15, 42, tzinfo=UTC)
_KEY = b"secret"


def _upload(**kwargs: object) -> AudioUpload:
    base: dict[str, object] = {"file_id": "f", "file_unique_id": "u", "duration_sec": 180}
    base.update(kwargs)
    return AudioUpload(**base)  # type: ignore[arg-type]


def test_tags_win_over_file_name_and_lose_channel_junk() -> None:
    name = track_name(_upload(
        title="Ауру (@music_kz)", performer="Қайрат Нұртас", file_name="x.mp3",
    ))
    assert (name.performer, name.title) == ("Қайрат Нұртас", "Ауру")


def test_file_name_is_split_on_spaced_dash_only() -> None:
    name = track_name(_upload(file_name="03. Ninety One - Қара-Торғай [www.zvuk.kz].mp3"))
    assert (name.performer, name.title) == ("Ninety One", "Қара-Торғай")


def test_missing_everything_gives_readable_placeholders() -> None:
    name = track_name(_upload())
    assert name.performer == UNKNOWN_PERFORMER
    assert name.title


def test_short_audio_is_not_music() -> None:
    assert not is_music(_upload(duration_sec=4))
    assert is_music(_upload(duration_sec=10))


def test_search_key_ignores_case_and_punctuation() -> None:
    assert search_key("  Қайрат  Нұртас — АУРУ!! ") == search_key("қайрат нұртас ауру")


def test_music_links_cover_section_track_and_playlist_with_source_tag() -> None:
    assert parse_music_link("music") == MusicLink()
    assert parse_music_link("ch-t_42") == MusicLink(track_id=42)
    assert parse_music_link("pl_AbC-12_x") == MusicLink(playlist_code="AbC-12_x")
    assert parse_music_link("m_42") is None
    assert parse_music_link(None) is None


def test_stream_link_is_valid_until_expiry_and_bound_to_track() -> None:
    expires = stream_expiry(_NOW)
    signature = stream_signature(_KEY, 7, expires)
    assert verify_stream(_KEY, 7, expires, signature, _NOW)
    assert not verify_stream(_KEY, 8, expires, signature, _NOW)
    assert not verify_stream(b"other", 7, expires, signature, _NOW)
    later = datetime.fromtimestamp(expires, UTC) + timedelta(seconds=1)
    assert not verify_stream(_KEY, 7, expires, signature, later)


def test_stream_link_is_stable_within_an_hour_for_browser_cache() -> None:
    assert stream_expiry(_NOW) == stream_expiry(_NOW.replace(minute=5))


def test_playlist_title_is_trimmed_and_never_empty() -> None:
    assert playlist_title("   ") == DEFAULT_TITLE
    assert len(playlist_title("ә" * 500)) == TITLE_MAX
    assert len(new_share_code()) <= 16


def test_chart_escapes_names_and_calls_for_missing_songs() -> None:
    chart = WeeklyChart(
        week=date(2026, 11, 23),
        top=(ChartEntry("<b>Ән</b>", "A&B", 12),),
        new_tracks=5,
        wanted=("Жоқ ән",),
    )
    text = render_chart(chart)
    assert "&lt;b&gt;Ән&lt;/b&gt;" in text and "A&amp;B" in text
    assert "Жоқ ән" in text and "5 жаңа ән" in text


def test_empty_chart_is_not_posted() -> None:
    assert not has_content(WeeklyChart(date(2026, 11, 23), (), 3, ("x",)))
