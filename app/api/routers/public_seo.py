"""Публичные SSR-страницы для поисковой индексации (SEO). БЕЗ авторизации и без /api-префикса.

Google не индексирует SPA Mini App (контент рисует JS после initData-гейта → краулер видит
пустую оболочку). Поэтому по человекочитаемым URL мы отдаём НАСТОЯЩИЙ, отрендеренный на
сервере HTML с мета-тегами, Open Graph и микроразметкой schema.org — из тех же данных БД.

Маршруты (Caddy проксирует их на api ДО SPA-фолбэка):
  GET /m/<id>-<slug>   — страница фильма (canonical-редирект, если хвост slug не совпал)
  GET /catalog         — хаб-каталог: разделы + страница карточек (`?page=N`)
  GET /catalog?q=…     — результаты поиска: та же страница под `noindex, follow`
  GET /catalog/<slug>  — страница-хаб: раздел (`kids`), подборка (`new`, `popular`)
                         или год (`2024`) — широкие запросы + 2-й уровень связей
  GET /sitemap.xml     — карта сайта (главная + хабы со всеми их страницами + все фильмы)
  GET /robots.txt      — разрешение обхода + ссылка на sitemap

Перелинковка устроена в три уровня: каталог → раздел → фильм → похожие фильмы. Раньше
карточка фильма была тупиком (единственная ссылка вела назад в каталог), а на весь сайт
приходилась одна хаб-страница — по широким запросам ранжироваться было нечему.

⚠️ **Хабы листаются, а не растут.** Страница отдаёт `SEO_PAGE_SIZE` карточек: каждая тянет
свой постер, и один документ на весь каталог тяжелел с каждым залитым фильмом — на сотне
карточек это уже мегабайты картинок, которые краулер бросает не догрузив. Правила самой
пагинации (canonical, `?page=1`, номера) — в `domain/seo/pagination`.

⚠️ **Ни одна страница не читает каталог целиком.** Свой срез страница берёт запросом с
`LIMIT`, счётчики разделов — одним `GROUP BY`, похожие — отдельным запросом. Единственное
исключение — sitemap: он обязан перечислить каждый URL.

«Автогенерация при загрузке» — это и есть рендер из БД на лету: как только `/add` сохранил
фильм, его страница и строка sitemap появляются сразу и всегда свежие (без файлов на диске).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.application.ports.storage import thumb_url
from app.application.services.catalog_service import SEO_PAGE_SIZE, CatalogService
from app.application.services.seo_service import HubSeo, MovieSeo, SeoBuilder
from app.config.settings import AppConfig
from app.domain.catalog.categories import Category, get_category
from app.domain.entities.movie import Movie
from app.domain.seo.hubs import (
    COLLECTIONS,
    Hub,
    collection_hub,
    indexable_years,
    parse_year,
    resolve_hub,
)
from app.domain.seo.pagination import Pagination, page_count, paginate


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
# Фильтр `thumb`: в сетках страниц постер показывается в 120–200 px, и грузить туда
# крупную копию (вдвое тяжелее) незачем — на странице их несколько десятков. Правило
# имени берём из контракта хранилища, чтобы шаблон не сочинял пути сам.
_TEMPLATES.env.filters["thumb"] = thumb_url
_LEADING_ID = re.compile(r"^(\d+)")

# Сколько «похожих» показываем в подвале карточки фильма. Смысл блока — не рекомендации,
# а перелинковка: без него каждая страница фильма была тупиком, из которого краулер
# уходил только назад в каталог.
_RELATED_LIMIT = 6
# Сколько результатов поиска рисуем. Страница поиска не индексируется, листать её незачем —
# но и бесконечной она быть не должна: у неё те же постеры, что у каталога.
_SEARCH_LIMIT = SEO_PAGE_SIZE
# Ниже этой длины поиск не запускаем: одна буква совпадает почти со всем каталогом.
_SEARCH_MIN_LEN = 2

_CATALOG_PATH = "/catalog"


def _category_links(counts: Sequence[tuple[str, int]]) -> list[_CategoryLink]:
    """Непустые разделы со счётчиками. Порядок задаёт сервис (каноничный по справочнику).

    Слаг, которого нет в справочнике, ссылки не получает — вести его некуда (страницы
    такого раздела не существует, `hub_page` отдаст 404).
    """
    return [
        _CategoryLink(category, f"{_CATALOG_PATH}/{slug}", count)
        for slug, count in counts
        if (category := get_category(slug)) is not None
    ]


@dataclass(frozen=True, slots=True)
class _Shelf:
    """Врезка подборки на чужой странице: подпись, ссылка «все» и несколько карточек."""

    title: str
    path: str
    items: list[_CatalogItem]


async def _shelves(
    catalog: CatalogService, seo: SeoBuilder, *, exclude: str | None = None
) -> list[_Shelf]:
    """Врезки «Жаңа түскен» и «Танымал» для перелинковки.

    Смысл — ссылки, а не витрина: врезка короткая и ведёт на страницу подборки, откуда
    краулер уходит дальше по её пагинации. Текущую страницу из врезок исключаем — на
    `/catalog/new` блок «новинки» был бы тем же списком дважды.
    """
    shelves: list[_Shelf] = []
    for collection in COLLECTIONS.values():
        if collection.slug == exclude:
            continue
        hub = collection_hub(collection)
        items = [
            _CatalogItem(m, seo.movie_seo(m))
            for m in await catalog.seo_shelf(hub)
            if m.id is not None
        ]
        if items:
            shelves.append(_Shelf(title=collection.shelf_kk, path=hub.path, items=items))
    return shelves


def _year_links(
    year_counts: dict[int, int], *, exclude: str | None = None
) -> list[tuple[str, str]]:
    """Ссылки на страницы годов: (подпись, путь). Только годы, у которых страница есть."""
    return [
        (str(year), f"{_CATALOG_PATH}/{year}")
        for year in indexable_years(year_counts)
        if str(year) != exclude
    ]


def _newest(movies: list[Movie]) -> str | None:
    """Дата самого свежего фильма набора — `lastmod` страницы-хаба.

    Хаб «изменился» ровно тогда, когда в нём появился новый фильм: этой даты достаточно,
    чтобы автоотправка в Indexing API заметила изменение и переслала страницу.
    """
    dates = [m.created_at.date() for m in movies if m.created_at is not None]
    return max(dates).isoformat() if dates else None


async def _paged(
    catalog: CatalogService,
    seo: SeoBuilder,
    *,
    hub: Hub | None,
    path: str,
    page: int,
) -> tuple[list[_CatalogItem], Pagination, int]:
    """Срез хаба + пагинация + total. Страница за последней — 404 (пустых не отдаём)."""
    slice_ = await catalog.seo_page(hub=hub, page=page)
    pager = paginate(path=path, page=page, total=slice_.total, size=slice_.limit)
    if page > pager.pages:
        raise HTTPException(status_code=404, detail="page out of range")
    items = [_CatalogItem(m, seo.movie_seo(m)) for m in slice_.items if m.id is not None]
    return items, pager, slice_.total


def _page_gate(request: Request, path: str, page: int) -> RedirectResponse | None:
    """Канонизация номера страницы: мусор → 404, `?page=1` → 301 на чистый URL.

    404, а не ошибка валидации: `?page=0` — это «такой страницы нет», и в отчётах
    Search Console оно должно выглядеть именно так, а не как сбой сервера.
    """
    if page < 1:
        raise HTTPException(status_code=404, detail="page out of range")
    if page == 1 and request.query_params.get("page") is not None:
        # Один документ обязан иметь один адрес, иначе это дубль чистого URL.
        return RedirectResponse(url=path, status_code=301)
    return None

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

    related = [
        _CatalogItem(m, seo.movie_seo(m))
        for m in await catalog.related(movie, _RELATED_LIMIT)
        if m.id is not None
    ]

    # Ссылки-выходы со страницы: год выпуска и подборки. Карточек тут не рисуем — их
    # место в блоке похожих; страница фильма набирает ссылки, а не вес.
    #
    # Год становится ссылкой только если его страница существует (порог
    # `hubs.YEAR_MIN_MOVIES`): ссылка на 404 хуже отсутствия ссылки.
    year_path: str | None = None
    if movie.year is not None:
        counts = await catalog.year_counts()
        if movie.year in indexable_years(counts):
            year_path = f"{_CATALOG_PATH}/{movie.year}"

    return _TEMPLATES.TemplateResponse(
        request,
        "movie.html",
        {
            "movie": movie,
            "seo": meta,
            "related": related,
            "year_path": year_path,
            "collections": [
                (c.heading_kk, collection_hub(c).path) for c in COLLECTIONS.values()
            ],
            "site_url": config.public_origin.rstrip("/"),
        },
    )


@router.get("/catalog", response_class=HTMLResponse)
async def catalog_page(
    request: Request,
    catalog: FromDishka[CatalogService],
    seo: FromDishka[SeoBuilder],
    config: FromDishka[AppConfig],
    page: int = Query(1),
    q: str = Query("", max_length=100),
) -> Response:
    """Хаб-каталог: разделы + страница карточек. С `?q=` — результаты серверного поиска.

    Поиск живёт здесь, а не на своём пути: страницу результатов Google индексировать не
    рекомендует (`noindex`), поэтому отдельный адрес ей ничего не даёт, а `/catalog` уже
    проксируется на api и уже описан в robots.
    """
    site = config.public_origin.rstrip("/")
    query = " ".join(q.split())
    common = {
        "site_url": site,
        "bot_username": config.bot.username.lstrip("@"),
        "site_jsonld": seo.site_jsonld(),
        "categories": _category_links(await catalog.category_counts()),
        "query": query,
    }

    if query:
        found = (
            await catalog.search_movies(query) if len(query) >= _SEARCH_MIN_LEN else []
        )
        items = [
            _CatalogItem(m, seo.movie_seo(m)) for m in found[:_SEARCH_LIMIT] if m.id is not None
        ]
        # `noindex, follow`: страницу в индекс не пускаем, но ссылки с неё краулер
        # обходит — карточки фильмов от этого только выигрывают. Врезки и годы здесь
        # тоже ни к чему: человек ищет конкретное, а ссылки краулер собирает с хабов.
        return _TEMPLATES.TemplateResponse(
            request,
            "catalog.html",
            {
                **common,
                "items": items,
                "pager": None,
                "robots": "noindex, follow",
                "jsonld": "",
                "shelves": [],
                "years": [],
            },
        )

    if (redirect := _page_gate(request, _CATALOG_PATH, page)) is not None:
        return redirect
    items, pager, _ = await _paged(catalog, seo, hub=None, path=_CATALOG_PATH, page=page)

    return _TEMPLATES.TemplateResponse(
        request,
        "catalog.html",
        {
            **common,
            "items": items,
            "pager": pager,
            "robots": "index, follow, max-image-preview:large",
            "jsonld": _catalog_jsonld(site, items, pager),
            # Врезки и годы — только на первой странице: на второй они дают те же ссылки
            # ещё раз, а вес добавляют каждой.
            "shelves": await _shelves(catalog, seo) if pager.page == 1 else [],
            "years": _year_links(await catalog.year_counts()) if pager.page == 1 else [],
        },
    )


@router.get("/catalog/{slug}", response_class=HTMLResponse)
async def hub_page(
    slug: str,
    request: Request,
    catalog: FromDishka[CatalogService],
    seo: FromDishka[SeoBuilder],
    config: FromDishka[AppConfig],
    page: int = Query(1),
) -> Response:
    """Страница-хаб: раздел, подборка или год — один обработчик на все три.

    Существует ради широких запросов («мультики для детей на казахском», «новинки на
    казахском», «мультфильмы 2024»): по ним карточка отдельного фильма ранжироваться не
    может — нужна страница, которая целиком про эту тему. Побочно даёт второй уровень
    перелинковки: каталог → хаб → фильм.

    Какой именно хаб живёт по слагу, решает `domain/seo/hubs.resolve_hub` — там же порог,
    ниже которого год страницы не получает. Счётчики годов запрашиваем ТОЛЬКО когда слаг
    похож на год: разделам и подборкам этот запрос ни к чему.
    """
    year_counts = await catalog.year_counts() if parse_year(slug) is not None else {}
    hub = resolve_hub(slug, year_counts=year_counts)
    if hub is None:
        raise HTTPException(status_code=404, detail="hub not found")

    if (redirect := _page_gate(request, hub.path, page)) is not None:
        return redirect

    items, pager, total = await _paged(catalog, seo, hub=hub, path=hub.path, page=page)
    # Пустой хаб страницы не получает: тонкая страница без контента только вредит
    # (и в sitemap она тоже не попадёт — там тот же фильтр по непустым).
    if not total:
        raise HTTPException(status_code=404, detail="hub is empty")

    meta = seo.hub_seo(hub, count=total, page_suffix=pager.title_suffix)
    counts = await catalog.category_counts()
    site = config.public_origin.rstrip("/")

    return _TEMPLATES.TemplateResponse(
        request,
        "hub.html",
        {
            "items": items,
            "pager": pager,
            # Счётчик в подписи — по ВСЕМУ хабу, а не по видимым карточкам: иначе
            # на второй странице «186 фильм» превратилось бы в «48 фильм».
            "total": total,
            "seo": meta,
            "siblings": [c for c in _category_links(counts) if c.category.slug != slug],
            "site_url": site,
            "bot_username": config.bot.username.lstrip("@"),
            "jsonld": _hub_jsonld(site, meta, items, pager),
            "site_jsonld": seo.site_jsonld(),
            # Врезки и годы — только на первой странице (см. `catalog_page`).
            "shelves": await _shelves(catalog, seo, exclude=slug) if pager.page == 1 else [],
            "years": (
                _year_links(year_counts or await catalog.year_counts(), exclude=slug)
                if pager.page == 1
                else []
            ),
        },
    )


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap(
    catalog: FromDishka[CatalogService],
    seo: FromDishka[SeoBuilder],
    config: FromDishka[AppConfig],
) -> Response:
    """XML-карта: главная + хабы (со всеми страницами пагинации) + все фильмы.

    Единственное место, которому нужен весь каталог: карта обязана перечислить каждый URL.
    """
    site = config.public_origin.rstrip("/")
    movies = await catalog.all_movies()

    # Приоритет 1.0 — у каталога, а не у корня: корень отдаёт SPA
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
            f"{site}{_CATALOG_PATH}", priority="1.0", changefreq="daily", lastmod=_newest(movies)
        ),
        _url_entry(f"{site}/", priority="0.9", changefreq="daily", lastmod=_newest(movies)),
    ]
    # ⚠️ Страницы пагинации в карте обязательны: карточки, до которых можно дойти только
    # со второй страницы, иначе остаются без единой ссылки в карте — а именно по ней
    # Google узнаёт о новых URL быстрее всего.
    urls += _pagination_entries(f"{site}{_CATALOG_PATH}", len(movies), _newest(movies))

    # Подборки — тот же каталог в другом порядке, поэтому `lastmod` у них общий с ним,
    # и меняются они с каждым новым фильмом (`changefreq` daily, как у каталога).
    for collection in COLLECTIONS.values():
        hub = collection_hub(collection)
        urls.append(
            _url_entry(
                f"{site}{hub.path}", priority="0.9", changefreq="daily", lastmod=_newest(movies)
            )
        )
        urls += _pagination_entries(f"{site}{hub.path}", len(movies), _newest(movies))

    # Разделы идут ВЫШЕ карточек (0.9): по широким запросам ранжируются именно они.
    # Только непустые — ровно те, что реально отдают 200 (см. `hub_page`).
    for slug, count in await catalog.category_counts():
        if get_category(slug) is None:
            continue
        path = f"{_CATALOG_PATH}/{slug}"
        in_category = [m for m in movies if slug in m.categories]
        lastmod = _newest(in_category)
        urls.append(
            _url_entry(f"{site}{path}", priority="0.9", changefreq="weekly", lastmod=lastmod)
        )
        urls += _pagination_entries(f"{site}{path}", count, lastmod)

    # Годы: только те, что прошли порог `hubs.YEAR_MIN_MOVIES` — ровно те, что отдают 200.
    # Приоритет ниже разделов: спрос на «мультфильмы <год>» уже разделов по теме.
    year_counts = await catalog.year_counts()
    for year in indexable_years(year_counts):
        path = f"{_CATALOG_PATH}/{year}"
        lastmod = _newest([m for m in movies if m.year == year])
        urls.append(
            _url_entry(f"{site}{path}", priority="0.8", changefreq="monthly", lastmod=lastmod)
        )
        urls += _pagination_entries(f"{site}{path}", year_counts[year], lastmod)

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
        # Результаты поиска и так под `noindex`; закрыть их и здесь — чтобы краулер не
        # тратил бюджет обхода на бесконечные комбинации запросов.
        "Disallow: /catalog?q=\n"
        f"Sitemap: {site}/sitemap.xml\n"
    )
    return PlainTextResponse(content=body)


def _pagination_entries(loc: str, total: int, lastmod: str | None) -> list[str]:
    """Строки карты для страниц 2..N хаба. Первая уже перечислена по чистому URL.

    `loc` — абсолютный адрес хаба: правило «как выглядит URL страницы N» одно на карту
    и на сами страницы, поэтому URL строит та же `Pagination`, а не конкатенация здесь.
    """
    pages = page_count(total, SEO_PAGE_SIZE)
    pager = Pagination(path=loc, page=1, pages=pages)
    return [
        # Приоритет ниже, чем у первой страницы хаба: это тот же раздел, но глубже.
        _url_entry(pager.url(number), priority="0.7", changefreq="weekly", lastmod=lastmod)
        for number in range(2, pages + 1)
    ]


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


def _list_elements(
    site: str, items: list[_CatalogItem], pager: Pagination
) -> list[dict[str, object]]:
    """`ListItem`-элементы страницы. `position` продолжает нумерацию предыдущих страниц.

    Сквозная нумерация — не косметика: она говорит поисковику, что страницы пагинации
    части одного списка, а не три независимых списка с позициями 1..48.
    """
    offset = (pager.page - 1) * SEO_PAGE_SIZE
    return [
        {
            "@type": "ListItem",
            "position": offset + i + 1,
            "url": f"{site}{it.seo.path}",
            "name": it.seo.heading,
        }
        for i, it in enumerate(items)
    ]


def _as_script(data: dict[str, object]) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _catalog_jsonld(site: str, items: list[_CatalogItem], pager: Pagination) -> str:
    """ItemList микроразметка каталога — список ссылок на страницы фильмов ЭТОЙ страницы."""
    return _as_script(
        {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": "QazaqCinema — қазақша фильмдер каталогы",
            "numberOfItems": len(items),
            "itemListElement": _list_elements(site, items, pager),
        }
    )


def _hub_jsonld(
    site: str, meta: HubSeo, items: list[_CatalogItem], pager: Pagination
) -> str:
    """CollectionPage с вложенным ItemList — «это раздел, и вот что в нём»."""
    return _as_script(
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": f"{meta.heading} — {meta.heading_ru}",
            "url": f"{meta.canonical_url}{pager.canonical_suffix}",
            "description": meta.description,
            "inLanguage": "kk",
            "mainEntity": {
                "@type": "ItemList",
                "numberOfItems": len(items),
                "itemListElement": _list_elements(site, items, pager),
            },
        }
    )
