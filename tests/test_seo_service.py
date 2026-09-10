"""Тесты сборки SEO-метаданных публичных страниц (slug + SeoBuilder)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from app.application.services.seo_service import SeoBuilder
from app.domain.catalog.categories import CATEGORIES, Category, get_category
from app.domain.entities.movie import Movie
from app.domain.seo.hubs import COLLECTIONS, category_hub, collection_hub, year_hub
from app.domain.seo.slug import movie_slug, slugify, transliterate


def _unescape(raw: str) -> str:
    """В JSON-LD `< > &` экранированы под встраивание в <script> — вернуть как было."""
    return raw.replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&")


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
    return SeoBuilder("https://qazaqcinema.kz/", "qazaqcinema_bot")


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
    assert meta.canonical_url == "https://qazaqcinema.kz/m/7-shrek"


def test_heading_pairs_name_with_kazaksha() -> None:
    meta = _seo().movie_seo(_movie())
    assert meta.heading == "Шрек қазақша"
    assert "қазақша" in meta.title_tag


def test_telegram_deeplink_uses_startapp() -> None:
    meta = _seo().movie_seo(_movie())
    assert meta.telegram_url == "https://t.me/qazaqcinema_bot?startapp=m_7"


def test_og_image_prefers_hero_and_is_absolute() -> None:
    meta = _seo().movie_seo(_movie(hero_image_url="/posters/hero.jpg"))
    assert meta.og_image == "https://qazaqcinema.kz/posters/hero.jpg"


def test_og_image_falls_back_to_poster() -> None:
    meta = _seo().movie_seo(_movie(hero_image_url=None))
    assert meta.og_image == "https://qazaqcinema.kz/posters/abc.jpg"


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
    data = json.loads(_unescape(meta.jsonld))
    assert "keywords" in data and "қазақша" in data["keywords"]


def test_jsonld_is_valid_movie_schema() -> None:
    meta = _seo().movie_seo(_movie())
    data = json.loads(_unescape(meta.jsonld))
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
    assert "aggregateRating" not in json.loads(_unescape(meta.jsonld))


# ── страницы-хабы: разделы, подборки, годы ────────────────────────────────────
def test_category_hub_targets_broad_query_in_both_languages() -> None:
    """H1 — казахский, русская формулировка того же спроса обязана быть на странице.

    Смысл раздела: по «мультики для детей на казахском» карточка фильма ранжироваться
    не может, нужна страница, чей заголовок и текст — про этот запрос.
    """
    meta = _seo().hub_seo(category_hub(get_category("kids")), count=12)  # type: ignore[arg-type]

    assert meta.path == "/catalog/kids"
    assert meta.canonical_url == "https://qazaqcinema.kz/catalog/kids"
    assert meta.heading == "Балаларға арналған мультфильмдер"
    assert meta.heading_ru == "Мультики для детей на казахском языке"
    assert "мультики для детей" in meta.description.lower()
    assert "12" in meta.description  # размер раздела попадает в сниппет


def test_category_hub_falls_back_for_category_without_landing_text() -> None:
    """Новая категория в справочнике не должна оставаться без посадочного текста."""
    fresh = Category("horror", "Ужасы", "Қорқынышты")
    meta = _seo().hub_seo(category_hub(fresh))

    assert meta.heading == "Қорқынышты қазақша"
    assert meta.heading_ru == "Ужасы на казахском языке"
    assert meta.intro  # лид собран, а не пустой
    assert "QazaqCinema" in meta.keywords


def test_every_hub_description_fits_google_snippet() -> None:
    """Лимиты сниппета проверяем на ВСЕХ видах хабов, а не только на разделах."""
    hubs = (
        [category_hub(CATEGORIES[slug]) for slug in CATEGORIES]
        + [collection_hub(c) for c in COLLECTIONS.values()]
        + [year_hub(2024)]
    )
    for hub in hubs:
        meta = _seo().hub_seo(hub, count=5)
        assert len(meta.description) <= 160, hub.slug
        assert len(meta.title_tag) <= 65, hub.slug


def test_collection_hub_keywords_come_from_its_own_tags() -> None:
    """У подборки категории нет — спрос описан её тегами, иначе ключи были бы пустыми."""
    meta = _seo().hub_seo(collection_hub(COLLECTIONS["new"]), count=50)

    assert "новинки на казахском" in meta.keywords
    assert "QazaqCinema" in meta.keywords


def test_year_hub_keywords_name_the_year() -> None:
    meta = _seo().hub_seo(year_hub(2024), count=12)

    assert "2024" in meta.keywords
    assert "2024" in meta.title_tag


# ── блок «вопрос — ответ» ─────────────────────────────────────────────────────
def test_hub_faq_is_filled_and_mentions_the_page_topic() -> None:
    meta = _seo().hub_seo(category_hub(get_category("kids")), count=186)  # type: ignore[arg-type]

    assert meta.faq
    assert any("Мультики для детей" in item.question for item in meta.faq)
    assert any("186" in item.answer for item in meta.faq)


def test_faq_markup_repeats_the_visible_text() -> None:
    """⚠️ Скрытый от пользователя FAQ Google считает нарушением и снимает разметку."""
    meta = _seo().hub_seo(category_hub(get_category("anime")), count=7)  # type: ignore[arg-type]
    data = json.loads(_unescape(meta.faq_jsonld))

    assert data["@type"] == "FAQPage"
    questions = [q["name"] for q in data["mainEntity"]]
    answers = [q["acceptedAnswer"]["text"] for q in data["mainEntity"]]
    assert questions == [item.question for item in meta.faq]
    assert answers == [item.answer for item in meta.faq]


# ── поиск по сайту в сниппете ─────────────────────────────────────────────────
def test_site_jsonld_declares_a_working_search_endpoint() -> None:
    """SearchAction обязан указывать на живую страницу результатов — иначе это заявка ни о чём."""
    data = json.loads(_unescape(_seo().site_jsonld()))
    website = next(n for n in data["@graph"] if n["@type"] == "WebSite")
    action = website["potentialAction"]

    assert action["@type"] == "SearchAction"
    assert action["target"]["urlTemplate"] == (
        "https://qazaqcinema.kz/catalog?q={search_term_string}"
    )
    assert action["query-input"] == "required name=search_term_string"


# ── хлебные крошки ────────────────────────────────────────────────────────────
def test_movie_crumbs_lead_through_its_category() -> None:
    """Путь «Каталог → Раздел → Фильм»: у страницы появляется место в структуре сайта."""
    meta = _seo().movie_seo(_movie())

    assert [c.name for c in meta.crumbs] == ["Каталог", "Мультфильмдер", "Шрек қазақша"]
    assert [c.path for c in meta.crumbs] == ["/catalog", "/catalog/disney", ""]


def test_movie_without_categories_still_has_crumbs() -> None:
    meta = _seo().movie_seo(_movie(categories=[]))

    assert [c.name for c in meta.crumbs] == ["Каталог", "Шрек қазақша"]


def test_crumbs_jsonld_is_valid_breadcrumblist() -> None:
    meta = _seo().movie_seo(_movie())
    data = json.loads(meta.crumbs_jsonld)

    assert data["@type"] == "BreadcrumbList"
    items = data["itemListElement"]
    assert [i["position"] for i in items] == [1, 2, 3]
    assert items[1]["item"] == "https://qazaqcinema.kz/catalog/disney"
    # У последнего звена (текущая страница) ссылки нет — так требует schema.org.
    assert "item" not in items[-1]


def test_crumbs_jsonld_escaped_for_script_tag() -> None:
    """Название с «<» не имеет права разорвать <script> на странице."""
    meta = _seo().movie_seo(_movie(title_ru="A </script> B", title_kk="A", title_original=None))

    assert "</script>" not in meta.crumbs_jsonld
    assert "\\u003c" in meta.crumbs_jsonld


# ── живые (человеческие) написания запросов ───────────────────────────────────
def test_keywords_include_layout_friendly_spelling() -> None:
    """«казакша» без ә/қ — не опечатка, а набор с русской раскладки. Должен быть покрыт."""
    meta = _seo().movie_seo(_movie())
    kw = meta.keywords.lower()

    assert "шрек казакша" in kw
    assert "шрек қазақша" in kw  # грамотный вариант никуда не делся
    assert "казакша мультик" in kw
    assert "мультик каз" in kw


def test_visible_tags_show_human_spelling_of_the_title() -> None:
    """Видимый блок — единственное место, где живое написание реально читается Google'ом."""
    tags = _seo().movie_seo(_movie()).tags

    assert "Шрек казакша" in tags
    assert "Шрек қазақша" in tags
    assert len(tags) <= 14


def test_headings_stay_correctly_spelled() -> None:
    """H1/title/description остаются грамотными: ошибки живут только в тегах и keywords."""
    meta = _seo().movie_seo(_movie())

    assert "казакша" not in meta.heading.lower()
    assert "казакша" not in meta.title_tag.lower()
    assert "казакша" not in meta.description.lower()


# ── разметка сайта: варианты написания бренда ─────────────────────────────────
def test_site_jsonld_declares_brand_aliases() -> None:
    data = json.loads(_seo().site_jsonld())
    org, site = data["@graph"]

    assert org["@type"] == "Organization"
    assert site["@type"] == "WebSite"
    for node in (org, site):
        assert node["name"] == "QazaqCinema"
        assert "казак синема" in node["alternateName"]
        assert "Qazaq Cinema" in node["alternateName"]
        assert "казакша кино" in node["alternateName"]


def test_site_jsonld_links_website_to_its_publisher() -> None:
    """@id-связка: Google должен понять, что WebSite и Organization — одно и то же."""
    org, site = json.loads(_seo().site_jsonld())["@graph"]

    assert site["publisher"]["@id"] == org["@id"]
    assert org["sameAs"] == ["https://t.me/qazaqcinema_bot"]


# ── title страниц пагинации ───────────────────────────────────────────────────
def test_category_pages_get_distinct_titles() -> None:
    """Один <title> на все страницы раздела — это дубли в выдаче."""
    category = get_category("kids")
    hub = category_hub(category)  # type: ignore[arg-type]
    first = _seo().hub_seo(hub, count=186)
    second = _seo().hub_seo(hub, count=186, page_suffix=" — 2-бет")

    assert first.title_tag != second.title_tag
    assert second.title_tag.endswith(" — 2-бет")


def test_page_number_survives_the_title_clip() -> None:
    """⚠️ Место под номер вычитается ДО обрезки: иначе его срезало бы у длинной категории.

    «kids» — как раз такая: её заголовок не влезает в лимит целиком даже без номера.
    """
    long_named = category_hub(get_category("kids"))  # type: ignore[arg-type]

    meta = _seo().hub_seo(long_named, count=186, page_suffix=" — 10-бет")

    assert "10-бет" in meta.title_tag
    assert len(meta.title_tag) <= 65


def test_first_page_title_is_unchanged_by_the_suffix_rule() -> None:
    """Пустой суффикс не должен ничего сдвигать: первая страница живёт как жила."""
    hub = category_hub(get_category("anime"))  # type: ignore[arg-type]

    assert (
        _seo().hub_seo(hub, count=5).title_tag
        == _seo().hub_seo(hub, count=5, page_suffix="").title_tag
    )
