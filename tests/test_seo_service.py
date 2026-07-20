"""Тесты сборки SEO-метаданных публичных страниц (slug + SeoBuilder)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from app.application.services.seo_service import SeoBuilder
from app.domain.entities.movie import Movie
from app.domain.seo.slug import movie_slug, slugify, transliterate


def _movie(**kw: object) -> Movie:
    base: dict[str, object] = {
        "title_kk": "Шрек",
        "description": "Батпақтағы огр туралы ертегі.",
        "categories": ["disney", "comedy"],
        "poster_url": "/posters/abc.jpg",
        "telegram_file_id": "FILEID",
        "title_ru": "Шрек",
        "title_original": "Shrek",
        "year": 2001,
        "rating": 8.5,
        "play_count": 42,
        "id": 7,
        "created_at": datetime(2026, 7, 20, tzinfo=UTC),
    }
    base.update(kw)
    return Movie(**base)  # type: ignore[arg-type]


def _seo() -> SeoBuilder:
    return SeoBuilder("https://qazaqcinema.rehubpro.kz/", "qazaqcinema_bot")


# ── транслитерация / slug ─────────────────────────────────────────────────────
def test_transliterate_kazakh_specific_letters() -> None:
    # ә→a ғ→g қ→q ң→ng ө→o ұ→u ү→u і→i
    assert transliterate("әғқңөұүі") == "agqngouui"


def test_slugify_collapses_and_trims() -> None:
    assert slugify("Шрек 2 !!!") == "shrek-2"
    assert slugify("  Наруто: Ураганные хроники  ") == "naruto-uragannye-hroniki"


def test_movie_slug_has_leading_id() -> None:
    assert movie_slug(7, "Shrek") == "7-shrek"


def test_movie_slug_falls_back_to_id_when_tail_empty() -> None:
    # Название из символов, которые слаг не оставляет → только id, страница всё равно рабочая.
    assert movie_slug(9, "!!!") == "9"


# ── SeoBuilder ────────────────────────────────────────────────────────────────
def test_movie_seo_path_and_canonical() -> None:
    meta = _seo().movie_seo(_movie())
    assert meta.slug == "7-shrek"
    assert meta.path == "/m/7-shrek"
    assert meta.canonical_url == "https://qazaqcinema.rehubpro.kz/m/7-shrek"


def test_heading_pairs_name_with_kazaksha() -> None:
    meta = _seo().movie_seo(_movie())
    assert meta.heading == "Шрек қазақша"
    assert "қазақша" in meta.title_tag


def test_telegram_deeplink_uses_startapp() -> None:
    meta = _seo().movie_seo(_movie())
    assert meta.telegram_url == "https://t.me/qazaqcinema_bot?startapp=m_7"


def test_og_image_prefers_hero_and_is_absolute() -> None:
    meta = _seo().movie_seo(_movie(hero_image_url="/posters/hero.jpg"))
    assert meta.og_image == "https://qazaqcinema.rehubpro.kz/posters/hero.jpg"


def test_og_image_falls_back_to_poster() -> None:
    meta = _seo().movie_seo(_movie(hero_image_url=None))
    assert meta.og_image == "https://qazaqcinema.rehubpro.kz/posters/abc.jpg"


def test_description_within_limit_and_multilingual() -> None:
    meta = _seo().movie_seo(_movie())
    assert len(meta.description) <= 160
    assert "қазақ тілінде" in meta.description
    assert "на казахском" in meta.description


def test_keywords_cover_query_variants() -> None:
    kw = _seo().movie_seo(_movie(title_ru="Шрек", title_original="Shrek")).keywords
    # Обе формы названия × суффиксы (кириллица/латиница, «смотреть/онлайн/telegram»).
    for phrase in (
        "Шрек қазақша",
        "Shrek kazaksha",
        "Шрек на казахском",
        "Шрек смотреть онлайн",
        "Shrek telegram",
        "Шрек на казахском языке",
    ):
        assert phrase in kw, phrase


def test_keywords_include_category_broad_tags() -> None:
    # categories=["disney","comedy"] → «как ещё ищут» по категориям.
    kw = _seo().movie_seo(_movie()).keywords
    for phrase in (
        "қазақша disney мультфильмдері",
        "мультики для детей",
        "мультфильмы қазақша",  # комбинация категория × язык
        "комедии на казахском",
    ):
        assert phrase in kw, phrase


def test_keywords_include_universal_tags() -> None:
    kw = _seo().movie_seo(_movie()).keywords
    for phrase in ("фильмы telegram", "казахская озвучка", "қазақша мультфильмдер"):
        assert phrase in kw, phrase


def test_keywords_deduped_and_capped() -> None:
    from app.application.services.seo_service import _KEYWORDS_MAX

    kw = _seo().movie_seo(_movie()).keywords.split(", ")
    assert len(kw) == len(set(kw))  # без дублей
    assert len(kw) <= _KEYWORDS_MAX


def test_visible_tags_curated_and_bounded() -> None:
    tags = _seo().movie_seo(_movie(title_ru="Шрек")).tags
    assert tags  # непусто
    assert len(tags) <= 12
    assert "Шрек қазақша" in tags
    assert tags == list(dict.fromkeys(tags))  # без дублей


def test_jsonld_has_keywords_property() -> None:
    meta = _seo().movie_seo(_movie())
    raw = meta.jsonld.replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&")
    data = json.loads(raw)
    assert "keywords" in data and "қазақша" in data["keywords"]


def test_jsonld_is_valid_movie_schema() -> None:
    meta = _seo().movie_seo(_movie())
    # В JSON-LD < > & экранированы под встраивание в <script> — сначала разэкранируем.
    raw = meta.jsonld.replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&")
    data = json.loads(raw)
    assert data["@type"] == "Movie"
    assert data["name"] == "Шрек қазақша"
    assert "Shrek" in data["alternateName"]
    assert data["inLanguage"] == "kk"
    assert data["aggregateRating"]["ratingValue"] == 8.5
    assert data["aggregateRating"]["ratingCount"] == 42


def test_jsonld_escapes_script_breakout() -> None:
    # Описание с «</script>» не должно ломать встраивание в <script>.
    meta = _seo().movie_seo(_movie(description="злой </script><script>alert(1)</script>"))
    assert "</script>" not in meta.jsonld


def test_movie_without_id_rejected() -> None:
    with pytest.raises(ValueError):
        _seo().movie_seo(_movie(id=None))


def test_rating_absent_omits_aggregate_rating() -> None:
    meta = _seo().movie_seo(_movie(rating=None))
    raw = meta.jsonld.replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&")
    assert "aggregateRating" not in json.loads(raw)
