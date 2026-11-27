"""Публичные SSR-страницы музыки для Google — как страницы фильмов, основной вход извне.

`/music` — общая, `/music/<id>-<slug>` — трек, `/music/artist/<slug>` — исполнитель,
`/music/playlist/<код>` — открытый всем плейлист. Кнопка ведёт в бота через `start=`
(`seo-t_42`): человек оказывается в чате, бот отвечает кнопкой в Mini App, и присланные
песни лежат ровно там, откуда он слушает (та же причина, что у `movie_start_url`).

Ни одна часть не требует JS: страницы существуют для краулера и человека из поиска.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.application.services.music_catalog_service import MusicCatalogService
from app.application.services.playlist_service import PlaylistService
from app.config.settings import AppConfig
from app.domain.music.playlist import Playlist
from app.domain.music.seo import (
    MUSIC_PATH,
    artist_description,
    artist_key_from_slug,
    artist_path,
    artist_slug,
    artist_title_tag,
    clock,
    cover_gradient,
    initials,
    iso_duration,
    playlist_path,
    track_description,
    track_id_from_slug,
    track_path,
    track_title_tag,
)
from app.domain.music.track import Track

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
_INDEX_SHELF = 30
_INDEX_ARTISTS = 60
_INDEX_PLAYLISTS = 24
_CACHE = {"Cache-Control": "public, max-age=600"}
_SEARCH_LIMIT = 50
_SEARCH_MAX = 100

router = APIRouter(tags=["seo"], route_class=DishkaRoute, include_in_schema=False)


@dataclass(frozen=True, slots=True)
class _TrackView:
    """Трек для шаблона: подписи, адреса и цвет плитки посчитаны заранее."""

    id: int
    title: str
    performer: str
    path: str
    artist_path: str
    clock: str
    gradient: str
    initials: str


@dataclass(frozen=True, slots=True)
class _Block:
    title: str
    tracks: list[_TrackView]
    links: list[tuple[str, str]]


def _view(track: Track) -> _TrackView:
    assert track.id is not None
    return _TrackView(
        id=track.id,
        title=track.title,
        performer=track.performer,
        path=track_path(track.id, track.performer, track.title),
        artist_path=artist_path(track.performer),
        clock=clock(track.duration_sec),
        gradient=cover_gradient(f"{track.performer}{track.title}"),
        initials=initials(track.performer or track.title),
    )


def _views(tracks: list[Track]) -> list[_TrackView]:
    return [_view(t) for t in tracks if t.id is not None]


def _script(data: Mapping[str, object]) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _bot(config: AppConfig) -> str:
    return config.bot.username.lstrip("@")


def _site(config: AppConfig) -> str:
    return config.public_origin.rstrip("/")


def _recording(site: str, track: Track) -> dict[str, object]:
    assert track.id is not None
    return {
        "@type": "MusicRecording",
        "name": track.title,
        "url": f"{site}{track_path(track.id, track.performer, track.title)}",
        "duration": iso_duration(track.duration_sec),
        "byArtist": {
            "@type": "MusicGroup",
            "name": track.performer,
            "url": f"{site}{artist_path(track.performer)}",
        },
    }


def _base_context(request: Request, config: AppConfig) -> dict[str, object]:
    # `section` переключает шапку `base.html` на QazaqMusic и поиск по песням.
    return {
        "request": request,
        "site_url": _site(config),
        "bot_username": _bot(config),
        "section": "music",
    }


@router.get(MUSIC_PATH, response_class=HTMLResponse)
async def music_index(
    request: Request,
    music: FromDishka[MusicCatalogService],
    playlists: FromDishka[PlaylistService],
    config: FromDishka[AppConfig],
) -> Response:
    site = _site(config)
    home = await music.home()
    performers = await music.performers(_INDEX_ARTISTS)
    public = await playlists.list_public(_INDEX_PLAYLISTS)
    heading = "Қазақша әндер — Telegram-да тегін тыңдау"
    description = (
        "Қазақша және әлемдік әндер: тыңдаушылар өздері толтыратын каталог. Telegram-да тегін "
        "тыңдаңыз, плейлист жинаңыз. Казахские песни слушать онлайн бесплатно в Telegram."
    )[:160]
    blocks = [
        _Block("Танымал әндер", _views(home.popular[:_INDEX_SHELF]), []),
        _Block("Жаңа қосылған", _views(home.recent[:_INDEX_SHELF]), []),
        _Block(
            "Орындаушылар",
            [],
            [(f"{name} · {count}", artist_path(name)) for name, count in performers],
        ),
        _Block(
            "Тыңдаушылардың плейлистері",
            [],
            [(f"{p.title} · {p.track_count} ән", playlist_path(p.share_code)) for p in public],
        ),
    ]
    jsonld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": heading,
        "url": f"{site}{MUSIC_PATH}",
        "description": description,
        "hasPart": [_recording(site, t) for t in home.popular[:_INDEX_SHELF] if t.id is not None],
    }
    meta = {
        "title": "Қазақша әндер тыңдау — казахские песни слушать | QazaqMusic",
        "description": description,
        "canonical": f"{site}{MUSIC_PATH}",
        "og_type": "website",
        "heading": heading,
        "subtitle": "Әнді басыңыз — ол Telegram-да ойнайды. Жоқ әнді ботқа жіберіп, бәріне ашыңыз.",
        "telegram_url": f"https://t.me/{_bot(config)}?start=seo-music",
        "gradient": "linear-gradient(135deg, #7c3aed, #f472b6)",
        "initials": "♪",
        "crumbs": [("Музыка", None)],
        "jsonld": _script(jsonld),
    }
    return _TEMPLATES.TemplateResponse(
        request,
        "music_list.html",
        {
            **_base_context(request, config),
            "meta": meta,
            "blocks": [b for b in blocks if b.tracks or b.links],
        },
        headers=_CACHE,
    )


@router.get(f"{MUSIC_PATH}/artist/{{slug}}", response_class=HTMLResponse)
async def artist_page(
    slug: str,
    request: Request,
    music: FromDishka[MusicCatalogService],
    config: FromDishka[AppConfig],
) -> Response:
    page = await music.artist(artist_key_from_slug(slug))
    if page is None:
        raise HTTPException(status_code=404, detail="artist not found")
    canonical_slug = artist_slug(page.name)
    if slug != canonical_slug:
        return RedirectResponse(url=artist_path(page.name), status_code=301)
    site = _site(config)
    count = len(page.tracks)
    jsonld = {
        "@context": "https://schema.org",
        "@type": "MusicGroup",
        "name": page.name,
        "url": f"{site}{artist_path(page.name)}",
        "track": [_recording(site, t) for t in page.tracks],
    }
    meta = {
        "title": artist_title_tag(page.name, count),
        "description": artist_description(page.name, count),
        "canonical": f"{site}{artist_path(page.name)}",
        "og_type": "music.musician",
        "heading": f"{page.name} — барлық әндері",
        "subtitle": f"{count} ән · Telegram-да тегін тыңдау",
        "telegram_url": f"https://t.me/{_bot(config)}?start=seo-music",
        "gradient": cover_gradient(page.name),
        "initials": initials(page.name),
        "crumbs": [("Музыка", MUSIC_PATH), (page.name, None)],
        "jsonld": _script(jsonld),
    }
    blocks = [_Block("Әндері", _views(page.tracks), [])]
    return _TEMPLATES.TemplateResponse(
        request,
        "music_list.html",
        {**_base_context(request, config), "meta": meta, "blocks": blocks},
        headers=_CACHE,
    )


@router.get(f"{MUSIC_PATH}/playlist/{{code}}", response_class=HTMLResponse)
async def playlist_page(
    code: str,
    request: Request,
    playlists: FromDishka[PlaylistService],
    config: FromDishka[AppConfig],
) -> Response:
    view = await playlists.shared(code[:16])
    # Индексируем только открытые всем: ссылка «для друга» — не публикация.
    if view is None or not view.playlist.is_public or not view.tracks:
        raise HTTPException(status_code=404, detail="playlist not found")
    site = _site(config)
    playlist: Playlist = view.playlist
    count = len(view.tracks)
    jsonld = {
        "@context": "https://schema.org",
        "@type": "MusicPlaylist",
        "name": playlist.title,
        "url": f"{site}{playlist_path(playlist.share_code)}",
        "numTracks": count,
        "track": [_recording(site, t) for t in view.tracks],
    }
    performers = list(dict.fromkeys(t.performer for t in view.tracks))[:4]
    description = (
        f"«{playlist.title}» плейлисі: {count} ән — {', '.join(performers)}. "
        "Telegram-да тегін тыңдаңыз. Плейлист слушать онлайн."
    )[:160]
    meta = {
        "title": f"«{playlist.title}» плейлисі — {count} ән тыңдау | QazaqMusic"[:70],
        "description": description,
        "canonical": f"{site}{playlist_path(playlist.share_code)}",
        "og_type": "music.playlist",
        "heading": playlist.title,
        "subtitle": f"Тыңдаушы плейлисі · {count} ән",
        "telegram_url": f"https://t.me/{_bot(config)}?start=seo-pl_{playlist.share_code}",
        "gradient": cover_gradient(playlist.title),
        "initials": "♪",
        "crumbs": [("Музыка", MUSIC_PATH), (playlist.title, None)],
        "jsonld": _script(jsonld),
    }
    blocks = [_Block("Әндер", _views(view.tracks), [])]
    return _TEMPLATES.TemplateResponse(
        request,
        "music_list.html",
        {**_base_context(request, config), "meta": meta, "blocks": blocks},
        headers=_CACHE,
    )


@router.get(f"{MUSIC_PATH}/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    music: FromDishka[MusicCatalogService],
    config: FromDishka[AppConfig],
    q: str = "",
) -> Response:
    """Поиск песен из шапки. `noindex, follow` и `Disallow` в robots: страницы результатов
    Google индексировать не советует, а ссылки с них на треки пусть обходит.

    Ищет тем же ключом, что Mini App: «кайрат», «Qairat» и «Қайрат» — одно и то же.
    """
    query = " ".join(q.split())[:_SEARCH_MAX]
    if not query:
        return RedirectResponse(url=MUSIC_PATH, status_code=302)
    found = await music.search(query, _SEARCH_LIMIT, 0)
    site = _site(config)
    bot = _bot(config)
    meta = {
        "title": f"«{query}» — ән іздеу | QazaqMusic"[:70],
        "description": f"«{query}» бойынша табылған әндер — Telegram-да тегін тыңдау.",
        "canonical": f"{site}{MUSIC_PATH}",
        "robots": "noindex, follow",
        "og_type": "website",
        "heading": f"«{query}»",
        "subtitle": f"{len(found)} ән табылды" if found else "Әзірге табылмады",
        "telegram_url": f"https://t.me/{bot}?start=seo-music",
        "gradient": "linear-gradient(135deg, #7c3aed, #f472b6)",
        "initials": "🔍",
        "crumbs": [("Музыка", MUSIC_PATH), ("Іздеу", None)],
        "jsonld": _script({"@context": "https://schema.org", "@type": "SearchResultsPage"}),
        "empty_hint": (
            "Бұл ән каталогта әзірге жоқ. Оны Telegram-нан тауып, ботқа қайта жіберіңіз — "
            "ән бірден бәріне ашылады. Немесе ботта сұраныс қалдырыңыз."
        ),
    }
    blocks = [_Block("Табылған әндер", _views(found), [])] if found else []
    return _TEMPLATES.TemplateResponse(
        request,
        "music_list.html",
        {**_base_context(request, config), "meta": meta, "blocks": blocks, "query": query},
    )


@router.get(f"{MUSIC_PATH}/{{slug}}", response_class=HTMLResponse)
async def track_page(
    slug: str,
    request: Request,
    music: FromDishka[MusicCatalogService],
    config: FromDishka[AppConfig],
) -> Response:
    track_id = track_id_from_slug(slug)
    details = await music.details(track_id) if track_id is not None else None
    if details is None:
        raise HTTPException(status_code=404, detail="track not found")
    track = details.track
    assert track.id is not None
    canonical = track_path(track.id, track.performer, track.title)
    if f"{MUSIC_PATH}/{slug}" != canonical:
        # Старый хвост (переименовали) или голый id → один адрес на трек.
        return RedirectResponse(url=canonical, status_code=301)
    site = _site(config)
    telegram_url = f"https://t.me/{_bot(config)}?start=seo-t_{track.id}"
    jsonld = {
        "@context": "https://schema.org",
        **_recording(site, track),
        "potentialAction": {"@type": "ListenAction", "target": telegram_url},
    }
    meta = {
        "title": track_title_tag(track.performer, track.title),
        "description": track_description(track.performer, track.title, details.stats.listeners),
        "canonical": f"{site}{canonical}",
        "telegram_url": telegram_url,
        "jsonld": _script(jsonld),
    }
    playlists = [
        {"title": p.title, "count": p.track_count, "path": playlist_path(p.share_code)}
        for p in details.playlists
    ]
    return _TEMPLATES.TemplateResponse(
        request,
        "music_track.html",
        {
            **_base_context(request, config),
            "meta": meta,
            "track": _view(track),
            "stats": details.stats,
            "by_artist": _views(details.by_artist),
            "similar": _views(details.similar),
            "playlists": playlists,
        },
        headers=_CACHE,
    )
