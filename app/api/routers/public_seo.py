"""Публичные SSR-страницы для поисковой индексации (SEO). БЕЗ авторизации и без /api-префикса.

Google не индексирует SPA Mini App (контент рисует JS после initData-гейта → краулер видит
пустую оболочку). Поэтому по человекочитаемым URL мы отдаём НАСТОЯЩИЙ, отрендеренный на
сервере HTML с мета-тегами, Open Graph и микроразметкой schema.org — из тех же данных БД.

Маршруты (Caddy проксирует их на api ДО SPA-фолбэка):
  GET /m/<id>-<slug>  — страница фильма (canonical-редирект, если хвост slug не совпал)
  GET /catalog        — хаб-каталог: внутренние ссылки на все страницы фильмов
  GET /sitemap.xml    — карта сайта (все фильмы + главная + каталог)
  GET /robots.txt     — разрешение обхода + ссылка на sitemap

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
from app.application.services.seo_service import MovieSeo, SeoBuilder
from app.config.settings import AppConfig
from app.domain.entities.movie import Movie


@dataclass(frozen=True, slots=True)
class _CatalogItem:
    """Карточка каталога для шаблона: фильм + его SEO-мета (шаблон читает `it.movie`/`it.seo`)."""

    movie: Movie
    seo: MovieSeo

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
_LEADING_ID = re.compile(r"^(\d+)")

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

    return _TEMPLATES.TemplateResponse(
        request,
        "movie.html",
        {"movie": movie, "seo": meta, "site_url": config.public_origin.rstrip("/")},
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
            "site_url": site,
            "bot_username": config.bot.username.lstrip("@"),
            "jsonld": jsonld,
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

    urls: list[str] = [
        _url_entry(f"{site}/", priority="1.0", changefreq="daily"),
        _url_entry(f"{site}/catalog", priority="0.9", changefreq="daily"),
    ]
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
