"""SEO-шаблоны музыки собираются и экранируют пользовательские названия."""

from __future__ import annotations

from app.api.routers.music_seo import _TEMPLATES, _Block, _view
from app.application.ports.music import TrackStats
from app.domain.music.track import Track


def _track(track_id: int, title: str, performer: str) -> Track:
    return Track(
        id=track_id, title=title, performer=performer, duration_sec=214,
        telegram_file_id="f", file_unique_id=f"u{track_id}", uploader_id=1,
    )


def _base() -> dict[str, object]:
    return {"site_url": "https://qazaqcinema.kz", "bot_username": "qazaqcinema_bot"}


def test_track_page_renders_cta_stats_and_escapes_titles() -> None:
    html = _TEMPLATES.get_template("music_track.html").render(
        **_base(),
        meta={
            "title": "t", "description": "d", "canonical": "https://x/music/1",
            "telegram_url": "https://t.me/qazaqcinema_bot?start=seo-t_1", "jsonld": "{}",
        },
        track=_view(_track(1, "<script>Ауру</script>", "Қайрат Нұртас")),
        stats=TrackStats(listeners=37, playlists=5, saves=12),
        by_artist=[_view(_track(2, "Сен", "Қайрат Нұртас"))],
        similar=[],
        playlists=[{"title": "Той", "count": 4, "path": "/music/playlist/abc12345"}],
    )
    assert "&lt;script&gt;Ауру" in html and "<script>Ауру" not in html
    assert "37 адам тыңдады" in html and "start=seo-t_1" in html
    assert "/music/artist/kairat-nurtas" in html and "/music/playlist/abc12345" in html


def test_list_page_renders_blocks_and_links() -> None:
    html = _TEMPLATES.get_template("music_list.html").render(
        **_base(),
        meta={
            "title": "t", "description": "d", "canonical": "c", "og_type": "website",
            "heading": "Қазақша әндер", "subtitle": "s", "telegram_url": "https://t.me/x",
            "gradient": "red", "initials": "♪", "crumbs": [("Музыка", None)], "jsonld": "{}",
        },
        blocks=[
            _Block("Танымал", [_view(_track(3, "Ауру", "Қайрат Нұртас"))], []),
            _Block("Орындаушылар", [], [("Қайрат Нұртас · 2", "/music/artist/kairat-nurtas")]),
        ],
    )
    assert "/music/3-qairat-nurtas-auru" in html and "Орындаушылар" in html
