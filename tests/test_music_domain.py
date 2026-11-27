"""Правила музыки без БД: разбор названий, ссылки, подпись прослушивания, хит-парад."""

from __future__ import annotations

from datetime import date

from app.domain.music.chart import ChartEntry, WeeklyChart, has_content, render_chart
from app.domain.music.links import MusicLink, parse_music_link
from app.domain.music.playlist import DEFAULT_TITLE, TITLE_MAX, new_share_code, playlist_title
from app.domain.music.search import fold, words
from app.domain.music.track import (
    UNKNOWN_PERFORMER,
    AudioUpload,
    is_music,
    parse_name,
    search_key,
    track_name,
)


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


def test_fold_unifies_kazakh_russian_and_latin_spellings() -> None:
    same = ("Қайрат Нұртас", "Кайрат Нуртас", "Kairat Nurtas", "Qairat Nurtas", "KAIRATT nurtas")
    assert {fold(text) for text in same} == {"kairat nurtas"}
    assert fold("Мақпал Жүнісова") == fold("Makpal Zhunisova")
    assert fold("Скриптонит") in fold("Scriptonite")
    assert fold("Ninety One — Қара-Торғай!") == "nineti one kara torgai"


def test_query_words_drop_single_letters() -> None:
    assert words("a kairat b nurtas") == ["kairat", "nurtas"]


def test_mojibake_tags_come_back_as_cyrillic() -> None:
    cp1251 = "Кайрат".encode("cp1251").decode("latin-1")
    utf8 = "Сен".encode().decode("latin-1")
    name = track_name(_upload(title=utf8, performer=cp1251))
    assert (name.performer, name.title) == ("Кайрат", "Сен")
    assert track_name(_upload(title="Déjà vu", performer="Beyoncé")).performer == "Beyoncé"


def test_rename_text_needs_performer_dash_title() -> None:
    parsed = parse_name("Ninety One - Қара-Торғай")
    assert parsed is not None and (parsed.performer, parsed.title) == ("Ninety One", "Қара-Торғай")
    assert parse_name("Қара-Торғай") is None
    assert parse_name(" — Ауру") is None


def test_music_links_cover_section_track_and_playlist_with_source_tag() -> None:
    assert parse_music_link("music") == MusicLink()
    assert parse_music_link("ch-t_42") == MusicLink(track_id=42)
    assert parse_music_link("pl_AbC-12_x") == MusicLink(playlist_code="AbC-12_x")
    assert parse_music_link("m_42") is None
    assert parse_music_link(None) is None


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
