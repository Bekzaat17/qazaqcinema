"""Сборка SEO-метаданных фильма для публичной SSR-страницы.

Единая точка «как выглядит SEO»: из доменной сущности `Movie` строит заголовок, meta-
описание, ключевые слова, абсолютные URL (canonical, og:image), deep-link в Telegram и
микроразметку schema.org/Movie. Зависит ТОЛЬКО от домена (Movie, справочник категорий,
slug) и двух строк конфига (адрес сайта и @-имя бота) — без I/O, легко тестируется.

«Автогенерация при загрузке» достигается тем, что страница рендерится из БД на лету: как
только визард `/add` сохранил фильм, эта же сборка выдаёт готовую SEO-страницу и строку в
sitemap. Отдельного шага генерации файлов нет — источник правды один (БД).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.catalog.categories import Category, get_category
from app.domain.entities.movie import Movie
from app.domain.seo.slug import movie_slug

# Бренд в конце <title> и микроразметке.
_BRAND = "QazaqCinema"
# Предел meta description (Google показывает ~155–160 символов — длиннее просто обрежется).
_DESC_MAX = 160
# Потолок числа ключевых фраз (дедуп + обрезка) — чтобы meta keywords не раздувалась бесконечно.
_KEYWORDS_MAX = 90

# ── Данные генерации ключевых запросов (расширять здесь, без правки логики) ─────────────
# Как ищут КОНКРЕТНЫЙ фильм: каждое название (ru/kk/оригинал) × эти суффиксы. Покрывает
# кириллицу/латиницу/раскладки и разные формулировки («смотреть», «онлайн», «telegram»…).
_NAME_SUFFIXES: tuple[str, ...] = (
    "қазақша",
    "қазақша көру",
    "қазақша толық нұсқа",
    "казахша",
    "kazaksha",
    "на казахском",
    "на казахском языке",
    "смотреть на казахском",
    "смотреть онлайн",
    "онлайн",
    "telegram",
    "мультфильм",
)

# Шаблоны комбинаций «категория × язык/площадка» (ru/kk-подписи подставляются в нижнем регистре).
_CATEGORY_PATTERNS: tuple[str, ...] = (
    "{ru} қазақша",
    "қазақша {kk}",
    "{ru} на казахском",
    "{kk} онлайн",
    "{ru} telegram",
)

# Широкие «как ещё могут искать» по категории (данные — легко дополнять новыми фразами/slug'ами).
_CATEGORY_TAGS: dict[str, tuple[str, ...]] = {
    "disney": ("қазақша disney мультфильмдері", "disney қазақша", "дисней на казахском",
               "уолт дисней қазақша", "мультики для детей"),
    "anime": ("аниме қазақша", "аниме на казахском", "аниме telegram", "аниме көру қазақша"),
    "film": ("фильмы на казахском", "фильмдер қазақша", "фильмы telegram", "кино қазақша"),
    "serial": ("сериалы на казахском", "сериалдар қазақша", "телехикая қазақша"),
    "short": ("қысқа метражды фильмдер", "короткометражки на казахском"),
    "otandyq": ("отандық мультфильмдер", "қазақстандық мультфильмдер", "казахские мультфильмы"),
    "kids": ("мультики для детей", "балаларға арналған мультфильмдер", "балалар мультфильмдері",
             "детские мультфильмы на казахском"),
    "girls": ("қыздарға арналған мультфильмдер", "мультики для девочек"),
    "boys": ("ұлдарға арналған мультфильмдер", "мультики для мальчиков"),
    "family": ("отбасылық фильмдер", "мультики для всей семьи", "жанұяға арналған кино"),
    "adventure": ("шытырман оқиғалы фильмдер", "приключения на казахском"),
    "comedy": ("күлкілі мультфильмдер", "комедии на казахском"),
    "fantasy": ("қиял-ғажайып фильмдер", "фэнтези на казахском"),
    "fairytale": ("қазақша ертегілер", "сказки на казахском", "ертегілер қазақша"),
    "learning": ("балаларға білім беру мультфильмдері", "развивающие мультики"),
    "classic": ("классикалық мультфильмдер қазақша", "советские мультфильмы на казахском"),
}

# Универсальные теги (для любого фильма — общий спрос на «қазақша контент»).
_BROAD_TAGS: tuple[str, ...] = (
    "қазақша мультфильмдер",
    "қазақша мультфильм",
    "мультфильмы на казахском",
    "мультфильмы на казахском языке",
    "мультики на казахском",
    "казахская озвучка",
    "қазақша дубляж",
    "қазақ тіліндегі мультфильмдер",
    "телеграм кинотеатр",
    "мультфильмы telegram",
    "фильмы telegram",
    "қазақша кино",
)


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
        title_tag = _clip(f"{heading} — көру онлайн | {_BRAND}", 65)

        year = f" ({movie.year})" if movie.year else ""
        lead = f"{display}{year} — қазақ тілінде (на казахском) онлайн көру."
        desc = _clip(f"{lead} {movie.description}" if movie.description else lead, _DESC_MAX)

        kw_list = self._keyword_list(names, cats)
        keywords = ", ".join(kw_list)
        tags = self._visible_tags(display, cats)
        jsonld = self._jsonld(
            movie, display, names, cats, canonical, og_image, telegram_url, keywords
        )

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
        )

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
            base += [f"{name} {s}" for s in _NAME_SUFFIXES]
        # 2) Широкие «как ещё ищут» по каждой присутствующей категории.
        for c in cats:
            base += list(_CATEGORY_TAGS.get(c.slug, ()))
        # 3) Комбинации «категория × язык/площадка» (подписи в нижнем регистре).
        for c in cats:
            ru, kk = c.title_ru.lower(), c.title_kk.lower()
            base += [p.format(ru=ru, kk=kk) for p in _CATEGORY_PATTERNS]
        # 4) Универсальный спрос + бренд.
        base += list(_BROAD_TAGS)
        base.append(_BRAND)
        return _unique(base)[:_KEYWORDS_MAX]

    def _visible_tags(self, display: str, cats: list[Category]) -> list[str]:
        """Курированный видимый блок «Осыны да іздейді» (~12) — без переспама на странице."""
        tags: list[str] = [
            f"{display} қазақша",
            f"{display} на казахском",
            f"{display} смотреть онлайн",
        ]
        for c in cats[:3]:
            tags.append(f"{c.title_ru.lower()} қазақша")
        for c in cats:
            tags += list(_CATEGORY_TAGS.get(c.slug, ())[:1])
        tags += ["қазақша мультфильмдер", "казахская озвучка"]
        return _unique(tags)[:12]

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
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        # Встраиваем в <script> — нейтрализуем < > & (иначе описание с «</script>» ломает страницу).
        return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _iso_date(dt: datetime | None) -> str:
    return dt.date().isoformat() if dt is not None else datetime.now().date().isoformat()
