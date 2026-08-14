"""Публичные SSR-страницы для поисковой индексации (SEO). БЕЗ авторизации и без /api-префикса.

Google не индексирует SPA Mini App (контент рисует JS после initData-гейта → краулер видит
пустую оболочку). Поэтому по человекочитаемым URL мы отдаём НАСТОЯЩИЙ, отрендеренный на
сервере HTML с мета-тегами, Open Graph и микроразметкой schema.org — из тех же данных БД.

Маршруты (Caddy проксирует их на api ДО SPA-фолбэка):
  GET /m/<id>-<slug>   — страница фильма (canonical-редирект, если хвост slug не совпал)
  GET /catalog         — хаб-каталог: ссылки на разделы и на все страницы фильмов
  GET /catalog/<slug>  — посадочная страница раздела (широкие запросы + 2-й уровень связей)
  GET /sitemap.xml     — карта сайта (главная + каталог + разделы + все фильмы)
  GET /robots.txt      — разрешение обхода + ссылка на sitemap

Перелинковка устроена в три уровня: каталог → раздел → фильм → похожие фильмы. Раньше
карточка фильма была тупиком (единственная ссылка вела назад в каталог), а на весь сайт
приходилась одна хаб-страница — по широким запросам ранжироваться было нечему.

«Автогенерация при загрузке» — это и есть рендер из БД на лету: как только `/add` сохранил
фильм, его страница и строка sitemap появляются сразу и всегда свежие (без файлов на диске).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.application.services.catalog_service import CatalogService
from app.application.services.seo_service import CategorySeo, MovieSeo, SeoBuilder
from app.config.settings import AppConfig
from app.domain.catalog.categories import CATEGORIES, Category, get_category
from app.domain.entities.movie import Movie


@dataclass(frozen=True, slots=True)
class _CatalogItem:
    """Карточка каталога для шаблона: фильм + его SEO-мета (шаблон читает `it.movie`/`it.seo`)."""

    movie: Movie
    seo: MovieSeo


@dataclass(frozen=True, slots=True)
class _CategoryLink:
    """Ссылка на раздел в навигации каталога: подписи + путь + счётчик."""

    category: Category
    path: str
    count: int

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
_LEADING_ID = re.compile(r"^(\d+)")

# Сколько «похожих» показываем в подвале карточки фильма. Смысл блока — не рекомендации,
# а перелинковка: без него каждая страница фильма была тупиком, из которого краулер
# уходил только назад в каталог.
_RELATED_LIMIT = 6


def _category_links(movies: list[Movie]) -> list[_CategoryLink]:
    """Непустые категории со счётчиками, в каноничном порядке справочника."""
    counts: dict[str, int] = {}
    for m in movies:
        for slug in m.categories:
            counts[slug] = counts.get(slug, 0) + 1
    return [
        _CategoryLink(CATEGORIES[slug], f"/catalog/{slug}", counts[slug])
        for slug in CATEGORIES
        if counts.get(slug)
    ]


def _newest(movies: list[Movie]) -> str | None:
    """Дата самого свежего фильма набора — `lastmod` страницы-хаба.

    Хаб «изменился» ровно тогда, когда в нём появился новый фильм: этой даты достаточно,
    чтобы автоотправка в Indexing API заметила изменение и переслала страницу.
    """
    dates = [m.created_at.date() for m in movies if m.created_at is not None]
    return max(dates).isoformat() if dates else None


def _related(movies: list[Movie], current: Movie) -> list[Movie]:
    """Фильмы, делящие с текущим хотя бы одну категорию. Больше общих категорий — выше."""
    own = set(current.categories)
    if not own:
        return []
    scored = [
        (len(own & set(m.categories)), m)
        for m in movies
        if m.id is not None and m.id != current.id and own & set(m.categories)
    ]
    scored.sort(key=lambda pair: (-pair[0], -(pair[1].id or 0)))
    return [m for _, m in scored[:_RELATED_LIMIT]]

router = APIRouter(tags=["seo"], route_class=DishkaRoute, include_in_schema=False)


@router.get("/m/{slug}", response_class=HTMLResponse)
async def movie_page(
    slug: str,
    request: Request,
    catalog: FromDishka[CatalogService],
    seo: FromDishka[SeoBuilder],
    config: FromDishka[AppConfig],
) -> Response:
    """Страница фильма. id берём из ведущего числа slug'а; хвост — только для людей/URL."""
    match = _LEADING_ID.match(slug)
    if match is None:
        raise HTTPException(status_code=404, detail="not found")
    movie = await catalog.get_movie(int(match.group(1)))
    if movie is None:
        raise HTTPException(status_code=404, detail="movie not found")

    meta = seo.movie_seo(movie)
    # Канонизация: `/m/42` или `/m/42-старый-хвост` → 301 на актуальный `/m/42-<slug>`
    # (одна страница = один URL, без дублей для поисковика).
    if slug != meta.slug:
        return RedirectResponse(url=meta.path, status_code=301)

    all_movies = await catalog.all_movies()
    related = [_CatalogItem(m, seo.movie_seo(m)) for m in _related(all_movies, movie)]

    return _TEMPLATES.TemplateResponse(
        request,
        "movie.html",
        {
            "movie": movie,
            "seo": meta,
            "related": related,
            "site_url": config.public_origin.rstrip("/"),
        },
    )


@router.get("/catalog", response_class=HTMLResponse)
async def catalog_page(
    request: Request,
    catalog: FromDishka[CatalogService],
    seo: FromDishka[SeoBuilder],
    config: FromDishka[AppConfig],
) -> Response:
    """Хаб-каталог: карточки-ссылки на все страницы фильмов (внутренняя перелинковка для SEO)."""
    site = config.public_origin.rstrip("/")
    movies = await catalog.all_movies()
    items = [_CatalogItem(m, seo.movie_seo(m)) for m in movies if m.id is not None]

    jsonld = _catalog_jsonld(site, items)
    return _TEMPLATES.TemplateResponse(
        request,
        "catalog.html",
        {
            "items": items,
            "categories": _category_links(movies),
            "site_url": site,
            "bot_username": config.bot.username.lstrip("@"),
            "jsonld": jsonld,
            "site_jsonld": seo.site_jsonld(),
        },
    )


@router.get("/catalog/{slug}", response_class=HTMLResponse)
async def category_page(
    slug: str,
    request: Request,
    catalog: FromDishka[CatalogService],
    seo: FromDishka[SeoBuilder],
    config: FromDishka[AppConfig],
) -> Response:
    """Посадочная страница раздела.

    Существует ради широких запросов («мультики для детей на казахском»): по ним карточка
    отдельного фильма ранжироваться не может — нужна страница, которая целиком про эту тему.
    Побочно даёт второй уровень перелинковки: каталог → раздел → фильм.
    """
    category = get_category(slug)
    if category is None:
        raise HTTPException(status_code=404, detail="category not found")

    movies = await catalog.all_movies()
    picked = [m for m in movies if m.id is not None and slug in m.categories]
    # Пустой раздел страницы не получает: тонкая страница без контента только вредит
    # (и в sitemap она тоже не попадёт — там тот же фильтр по непустым).
    if not picked:
        raise HTTPException(status_code=404, detail="category is empty")

    site = config.public_origin.rstrip("/")
    items = [_CatalogItem(m, seo.movie_seo(m)) for m in picked]
    meta = seo.category_seo(category, count=len(items))

    return _TEMPLATES.TemplateResponse(
        request,
        "category.html",
        {
            "items": items,
            "seo": meta,
            "siblings": [c for c in _category_links(movies) if c.category.slug != slug],
            "site_url": site,
            "bot_username": config.bot.username.lstrip("@"),
            "jsonld": _category_jsonld(site, meta, items),
            "site_jsonld": seo.site_jsonld(),
        },
    )


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap(
    catalog: FromDishka[CatalogService],
    seo: FromDishka[SeoBuilder],
    config: FromDishka[AppConfig],
) -> Response:
    """XML-карта: главная + каталог + все фильмы (с датой и постером-картинкой)."""
    site = config.public_origin.rstrip("/")
    movies = await catalog.all_movies()

    # Приоритет 1.0 — у каталога, а не у корня (решение 2026-08-06): корень отдаёт SPA
    # Mini App (краулеру там показывать нечего, кроме «откройте в Telegram»), а /catalog —
    # настоящая серверная страница со всем контентом и перелинковкой на карточки фильмов.
    #
    # ⚠️ `lastmod` у ХАБОВ обязателен (иначе автоотправка в Indexing API их не заметит):
    # скрипт `/root/google_indexer.py` шлёт повторно только то, у чего дата свежее
    # прошлой отправки. Без даты каталог и разделы ушли бы в Google ровно один раз —
    # притом что меняются они чаще карточек: каждый новый фильм меняет и каталог, и
    # свои разделы. Дата хаба = дата самого свежего фильма внутри него.
    urls: list[str] = [
        _url_entry(
            f"{site}/catalog", priority="1.0", changefreq="daily", lastmod=_newest(movies)
        ),
        _url_entry(f"{site}/", priority="0.9", changefreq="daily", lastmod=_newest(movies)),
    ]
    # Разделы идут ВЫШЕ карточек (0.9): по широким запросам ранжируются именно они.
    # Только непустые — ровно те, что реально отдают 200 (см. `category_page`).
    for link in _category_links(movies):
        in_category = [m for m in movies if link.category.slug in m.categories]
        urls.append(
            _url_entry(
                f"{site}{link.path}",
                priority="0.9",
                changefreq="weekly",
                lastmod=_newest(in_category),
            )
        )
    for movie in movies:
        if movie.id is None:
            continue
        meta = seo.movie_seo(movie)
        lastmod = movie.created_at.date().isoformat() if movie.created_at is not None else None
        urls.append(
            _url_entry(
                meta.canonical_url,
                priority="0.8",
                changefreq="weekly",
                lastmod=lastmod,
                image=f"{site}{movie.poster_url}",
                image_title=meta.heading,
            )
        )

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    return Response(content=body, media_type="application/xml")


@router.get("/robots.txt", include_in_schema=False)
async def robots(config: FromDishka[AppConfig]) -> PlainTextResponse:
    site = config.public_origin.rstrip("/")
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /tg/\n"
        f"Sitemap: {site}/sitemap.xml\n"
    )
    return PlainTextResponse(content=body)


def _url_entry(
    loc: str,
    *,
    priority: str,
    changefreq: str,
    lastmod: str | None = None,
    image: str | None = None,
    image_title: str | None = None,
) -> str:
    parts = [f"  <loc>{xml_escape(loc)}</loc>"]
    if lastmod:
        parts.append(f"  <lastmod>{lastmod}</lastmod>")
    parts.append(f"  <changefreq>{changefreq}</changefreq>")
    parts.append(f"  <priority>{priority}</priority>")
    if image:
        img = [f"    <image:loc>{xml_escape(image)}</image:loc>"]
        if image_title:
            img.append(f"    <image:title>{xml_escape(image_title)}</image:title>")
        parts.append("  <image:image>\n" + "\n".join(img) + "\n  </image:image>")
    return "  <url>\n" + "\n".join(parts) + "\n  </url>"


def _catalog_jsonld(site: str, items: list[_CatalogItem]) -> str:
    """ItemList микроразметка каталога — список ссылок на страницы фильмов."""
    elements = [
        {
            "@type": "ListItem",
            "position": i + 1,
            "url": f"{site}{it.seo.path}",
            "name": it.seo.heading,
        }
        for i, it in enumerate(items)
    ]
    data = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "QazaqCinema — қазақша фильмдер каталогы",
        "numberOfItems": len(items),
        "itemListElement": elements,
    }
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _category_jsonld(site: str, meta: CategorySeo, items: list[_CatalogItem]) -> str:
    """CollectionPage с вложенным ItemList — «это раздел, и вот что в нём»."""
    data = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": f"{meta.heading} — {meta.heading_ru}",
        "url": meta.canonical_url,
        "description": meta.description,
        "inLanguage": "kk",
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(items),
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": i + 1,
                    "url": f"{site}{it.seo.path}",
                    "name": it.seo.heading,
                }
                for i, it in enumerate(items)
            ],
        },
    }
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
