"""Сборка SEO-метаданных фильма для публичной SSR-страницы.

Единая точка «как выглядит SEO»: из доменной сущности `Movie` строит заголовок, meta-
описание, ключевые слова, абсолютные URL (canonical, og:image), deep-link в Telegram и
микроразметку schema.org/Movie. Зависит ТОЛЬКО от домена (Movie, справочник категорий,
slug) и двух строк конфига (адрес сайта и @-имя бота) — без I/O, легко тестируется.

«Автогенерация при загрузке» достигается тем, что страница рендерится из БД на лету: как
только визард `/add` сохранил фильм, эта же сборка выдаёт готовую SEO-страницу и строку в
sitemap. Отдельного шага генерации файлов нет — источник правды один (БД).

Сами формулировки спроса и тексты посадочных страниц — данные в `domain/seo/keywords.py`
и `domain/seo/landing.py`: новая фраза или новая категория не требуют правок здесь.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.catalog.categories import Category, get_category
from app.domain.catalog.daily import TZ
from app.domain.entities.movie import Movie
from app.domain.seo.keywords import (
    BRAND,
    BRAND_ALIASES,
    BROAD_TAGS,
    CATEGORY_PATTERNS,
    CATEGORY_TAGS,
    NAME_SUFFIXES,
)
from app.domain.seo.landing import landing_for
from app.domain.seo.slug import movie_slug

# Предел meta description (Google показывает ~155–160 символов — длиннее просто обрежется).
_DESC_MAX = 160
# Потолок числа ключевых фраз (дедуп + обрезка) — чтобы meta keywords не раздувалась бесконечно.
_KEYWORDS_MAX = 90


def _escape_for_script(raw: str) -> str:
    """Нейтрализовать `< > &` для встраивания JSON в `<script>`.

    Без этого описание фильма, содержащее «</script>», разорвало бы блок и сломало страницу.
    """
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _clip(text: str, limit: int) -> str:
    """Обрезать по границе слова, добавив «…», если реально укоротили."""
    text = " ".join(text.split())  # схлопнуть пробелы/переводы строк
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" .,;:—-")
    return f"{cut}…"


def _unique(values: Sequence[str | None]) -> list[str]:
    """Непустые уникальные строки с сохранением порядка (для вариантов названия)."""
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        v = (v or "").strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


@dataclass(frozen=True, slots=True)
class Crumb:
    """Звено хлебных крошек: видимая подпись + путь (пустой у последнего, текущего)."""

    name: str
    path: str = ""


@dataclass(frozen=True, slots=True)
class MovieSeo:
    """Готовые строки для HTML-шаблона страницы фильма (всё уже абсолютное/экранируемое)."""

    slug: str
    path: str                 # /m/<slug>
    canonical_url: str        # абсолютный URL страницы
    title_tag: str            # содержимое <title>
    description: str          # meta description
    keywords: str             # meta keywords (полный CSV всех сгенерированных запросов)
    og_image: str             # абсолютный URL картинки (hero → постер)
    telegram_url: str         # deep-link t.me/<bot>?startapp=m_<id>
    heading: str              # H1: узнаваемое название + «қазақша»
    names: list[str]          # варианты названия (kk/ru/original) для показа
    categories: list[Category] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)  # видимый блок «похожих запросов» (курированный)
    jsonld: str = "{}"        # JSON-LD schema.org/Movie (готовая строка)
    crumbs: list[Crumb] = field(default_factory=list)      # видимая навигация
    crumbs_jsonld: str = "{}"  # BreadcrumbList отдельным <script> (Google читает оба блока)


@dataclass(frozen=True, slots=True)
class CategorySeo:
    """Готовые строки для посадочной страницы категории `/catalog/<slug>`."""

    slug: str
    path: str                 # /catalog/<slug>
    canonical_url: str
    title_tag: str
    description: str
    keywords: str
    heading: str              # H1 (казахский)
    heading_ru: str           # та же тема по-русски — видимый подзаголовок
    intro: str                # лид-абзац (kk + ru)
    tags: list[str] = field(default_factory=list)
    jsonld: str = "{}"
    crumbs: list[Crumb] = field(default_factory=list)
    crumbs_jsonld: str = "{}"


class SeoBuilder:
    """Строит `MovieSeo` из `Movie`. site_url — без хвостового «/»; bot_username — без «@»."""

    def __init__(self, site_url: str, bot_username: str) -> None:
        self._site = site_url.rstrip("/")
        self._bot = bot_username.lstrip("@")

    def _abs(self, path_or_url: str) -> str:
        if path_or_url.startswith(("http://", "https://")):
            return path_or_url
        return f"{self._site}/{path_or_url.lstrip('/')}"

    def _categories(self, movie: Movie) -> list[Category]:
        return [c for slug in movie.categories if (c := get_category(slug)) is not None]

    def movie_seo(self, movie: Movie) -> MovieSeo:
        if movie.id is None:
            raise ValueError("movie без id не может иметь публичную страницу")

        # Узнаваемое название ведём русским/оригиналом (по нему выше поисковый спрос),
        # казахское — обязательным вариантом рядом («Shrek қазақша»).
        display = movie.title_ru or movie.title_original or movie.title_kk
        names = _unique([movie.title_ru, movie.title_kk, movie.title_original])
        cats = self._categories(movie)

        slug = movie_slug(movie.id, display)
        path = f"/m/{slug}"
        canonical = f"{self._site}{path}"
        og_image = self._abs(movie.hero_image_url or movie.poster_url)
        telegram_url = f"https://t.me/{self._bot}?startapp=m_{movie.id}"

        heading = f"{display} қазақша"
        title_tag = _clip(f"{heading} — көру онлайн | {BRAND}", 65)

        year = f" ({movie.year})" if movie.year else ""
        lead = f"{display}{year} — қазақ тілінде (на казахском) онлайн көру."
        desc = _clip(f"{lead} {movie.description}" if movie.description else lead, _DESC_MAX)

        kw_list = self._keyword_list(names, cats)
        keywords = ", ".join(kw_list)
        tags = self._visible_tags(display, cats)
        jsonld = self._jsonld(
            movie, display, names, cats, canonical, og_image, telegram_url, keywords
        )

        # Крошки ведут через ГЛАВНУЮ категорию фильма (первую из списка): так у страницы
        # появляется путь «каталог → раздел → фильм», а не плоская посадка из ниоткуда.
        crumbs = [Crumb("Каталог", "/catalog")]
        if cats:
            crumbs.append(Crumb(cats[0].title_kk, f"/catalog/{cats[0].slug}"))
        crumbs.append(Crumb(heading))

        return MovieSeo(
            slug=slug,
            path=path,
            canonical_url=canonical,
            title_tag=title_tag,
            description=desc,
            keywords=keywords,
            og_image=og_image,
            telegram_url=telegram_url,
            heading=heading,
            names=names,
            categories=cats,
            tags=tags,
            jsonld=jsonld,
            crumbs=crumbs,
            crumbs_jsonld=self._crumbs_jsonld(crumbs),
        )

    def category_seo(
        self, category: Category, count: int = 0, page_suffix: str = ""
    ) -> CategorySeo:
        """Посадочная страница раздела: H1/текст под ШИРОКИЙ запрос, а не под название фильма.

        Тексты — данные (`domain/seo/landing.py`), включая дефолт для категории без записи.

        `page_suffix` — хвост номера страницы (`Pagination.title_suffix`). Место под него
        вычитается из лимита ДО обрезки: иначе на длинной категории номер срезало бы
        вместе с брендом, и у всех страниц пагинации оказался бы один и тот же <title> —
        то есть дубли в выдаче.
        """
        landing = landing_for(category)
        heading, heading_ru, intro = landing.heading_kk, landing.heading_ru, landing.intro

        path = f"/catalog/{category.slug}"
        canonical = f"{self._site}{path}"
        title_tag = _clip(f"{heading} — {heading_ru} | {BRAND}", 65 - len(page_suffix))
        title_tag += page_suffix

        # В description сразу обе формулировки + число позиций: сниппет отвечает на запрос
        # («сколько их и что это»), а не повторяет заголовок.
        amount = f" Каталогта {count} фильм." if count else ""
        desc = _clip(f"{heading_ru}.{amount} {intro}", _DESC_MAX)

        keywords = ", ".join(self._category_keywords(category, heading, heading_ru))
        tags = _unique([heading, heading_ru, *CATEGORY_TAGS.get(category.slug, ())])[:10]

        crumbs = [Crumb("Каталог", "/catalog"), Crumb(category.title_kk)]

        return CategorySeo(
            slug=category.slug,
            path=path,
            canonical_url=canonical,
            title_tag=title_tag,
            description=desc,
            keywords=keywords,
            heading=heading,
            heading_ru=heading_ru,
            intro=intro,
            tags=tags,
            jsonld="{}",  # проставляет роутер: список фильмов знает он, а не сборщик мета
            crumbs=crumbs,
            crumbs_jsonld=self._crumbs_jsonld(crumbs),
        )

    def site_jsonld(self) -> str:
        """Разметка самого сайта: как он называется и КАК ЕЩЁ его пишут.

        `alternateName` — штатный способ сказать Google «казак синема», «qazaq cinema»
        и «казакша кино» — это тот же сайт. В отличие от `meta keywords` (Google их
        игнорирует с 2009 года) этот сигнал он читает. Для домена без истории брендовые
        запросы — единственное, где реально можно выигрывать, поэтому написания важны.
        """
        organization = {
            "@type": "Organization",
            "@id": f"{self._site}/#org",
            "name": BRAND,
            "alternateName": list(BRAND_ALIASES),
            "url": self._site,
            "logo": f"{self._site}/logo.png",
            "sameAs": [f"https://t.me/{self._bot}"],
        }
        website = {
            "@type": "WebSite",
            "@id": f"{self._site}/#site",
            "name": BRAND,
            "alternateName": list(BRAND_ALIASES),
            "url": self._site,
            "inLanguage": ["kk", "ru"],
            "publisher": {"@id": f"{self._site}/#org"},
        }
        data = {"@context": "https://schema.org", "@graph": [organization, website]}
        return _escape_for_script(json.dumps(data, ensure_ascii=False, separators=(",", ":")))

    def _category_keywords(self, category: Category, heading: str, heading_ru: str) -> list[str]:
        ru, kk = category.title_ru.lower(), category.title_kk.lower()
        base = [heading, heading_ru]
        base += list(CATEGORY_TAGS.get(category.slug, ()))
        base += [p.format(ru=ru, kk=kk) for p in CATEGORY_PATTERNS]
        base += list(BROAD_TAGS)
        base.append(BRAND)
        return _unique(base)[:_KEYWORDS_MAX]

    def _crumbs_jsonld(self, crumbs: list[Crumb]) -> str:
        """BreadcrumbList: Google рисует путь вместо голого URL в сниппете."""
        items = [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": c.name,
                **({"item": f"{self._site}{c.path}"} if c.path else {}),
            }
            for i, c in enumerate(crumbs)
        ]
        data = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": items,
        }
        return _escape_for_script(json.dumps(data, ensure_ascii=False, separators=(",", ":")))

    def _keyword_list(self, names: list[str], cats: list[Category]) -> list[str]:
        """Полный список поисковых запросов под фильм (дедуп + обрезка до `_KEYWORDS_MAX`).

        Порядок = ценность: сперва запросы под КОНКРЕТНЫЙ фильм (имя × суффиксы по всем
        формам названия — кириллица/латиница/раскладки), затем широкие теги по категориям
        («қазақша disney мультфильмдері», «мультики для детей»), их комбинации и общий спрос.
        """
        base: list[str] = []
        # 1) Имя × суффиксы — по каждой форме названия (ru/kk/оригинал).
        for name in names:
            base.append(name)
            base += [f"{name} {s}" for s in NAME_SUFFIXES]
        # 2) Широкие «как ещё ищут» по каждой присутствующей категории.
        for c in cats:
            base += list(CATEGORY_TAGS.get(c.slug, ()))
        # 3) Комбинации «категория × язык/площадка» (подписи в нижнем регистре).
        for c in cats:
            ru, kk = c.title_ru.lower(), c.title_kk.lower()
            base += [p.format(ru=ru, kk=kk) for p in CATEGORY_PATTERNS]
        # 4) Универсальный спрос + бренд.
        base += list(BROAD_TAGS)
        base.append(BRAND)
        return _unique(base)[:_KEYWORDS_MAX]

    def _visible_tags(self, display: str, cats: list[Category]) -> list[str]:
        """Курированный видимый блок «Осыны да іздейді» (~12) — без переспама на странице.

        Первым идёт «<название> казакша» — не «қазақша»: именно так фразу набирают с
        обычной раскладки, и это ЕДИНСТВЕННЫЙ текст на странице с таким написанием
        (заголовок и описание — грамотные, портить их незачем).
        """
        tags: list[str] = [
            f"{display} қазақша",
            f"{display} казакша",
            f"{display} на казахском",
            f"{display} смотреть онлайн",
            f"{display} каз тилинде",
        ]
        for c in cats[:3]:
            tags.append(f"{c.title_ru.lower()} қазақша")
        for c in cats:
            tags += list(CATEGORY_TAGS.get(c.slug, ())[:1])
        tags += ["қазақша мультфильмдер", "казакша мультик", "казахская озвучка"]
        return _unique(tags)[:14]

    def _jsonld(
        self,
        movie: Movie,
        display: str,
        names: list[str],
        cats: list[Category],
        canonical: str,
        og_image: str,
        telegram_url: str,
        keywords: str,
    ) -> str:
        """schema.org/Movie — то, что даёт Google расширенный сниппет (карточку фильма)."""
        data: dict[str, object] = {
            "@context": "https://schema.org",
            "@type": "Movie",
            "name": f"{display} қазақша",
            "url": canonical,
            "image": og_image,
            "inLanguage": "kk",
            "keywords": keywords,
        }
        alt = [n for n in names if n != display]
        if alt:
            data["alternateName"] = alt
        if movie.description:
            data["description"] = movie.description
        if movie.year:
            data["datePublished"] = str(movie.year)
        if cats:
            data["genre"] = [c.title_ru for c in cats]
        if movie.rating is not None:
            data["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": round(movie.rating, 1),
                "bestRating": 10,
                "worstRating": 1,
                "ratingCount": max(movie.play_count, 1),
            }
        data["potentialAction"] = {
            "@type": "WatchAction",
            "target": telegram_url,
            "expectsAcceptanceOf": {
                "@type": "Offer",
                "category": "subscription",
                "availabilityStarts": _iso_date(movie.created_at),
            },
        }
        return _escape_for_script(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def _iso_date(dt: datetime | None) -> str:
    """Дата для микроразметки. Нет `created_at` (старые строки) → сегодняшняя МЕСТНАЯ.

    Именно местная и именно aware: контейнеры живут в UTC, и наивный `now()` рисовал бы
    в разметке вчерашний день с полуночи до 05:00 по Казахстану.
    """
    return (dt if dt is not None else datetime.now(TZ)).date().isoformat()
