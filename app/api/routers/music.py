"""Музыка в Mini App: каталог, «Менің музыкам», плейлисты и отправка в чат.

Как у фильмов, файлов сервер не отдаёт: «тыңдау» — это трек в чате с ботом. Ответы
персональные, поэтому в общий Redis-кэш каталога не попадают (как и избранное).
Музыка бесплатна: гейта подписки здесь нет ни на одной ручке.
"""

from __future__ import annotations

from datetime import UTC, datetime

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit
from app.api.schemas.music import (
    ArtistOut,
    CollectionDetailOut,
    CollectionOut,
    IdsOut,
    MusicHomeOut,
    MusicMeOut,
    MusicRequestIn,
    MusicRequestOut,
    PlaylistAddOut,
    PlaylistDetailOut,
    PlaylistIn,
    PlaylistOut,
    PlaylistPatch,
    SendOut,
    TrackDetailOut,
    TrackIdsIn,
    TrackOut,
    collection_detail,
    collection_out,
    tracks_out,
)
from app.application.services.music_catalog_service import MusicCatalogService
from app.application.services.music_delivery_service import (
    SEND_MAX,
    MusicDeliveryService,
    SendOutcome,
)
from app.application.services.music_library_service import MusicLibraryService
from app.application.services.playlist_service import PlaylistService, PlaylistView
from app.config.settings import AppConfig
from app.domain.entities.user import User
from app.domain.music.collections import get_collection
from app.domain.music.seo import artist_key_from_slug, artist_slug

# Лимиты — данные. Чтение щедрое: за одной вышкой (CGNAT) сидят сотни людей.
_read = Depends(rate_limit(limit=240, window_seconds=60, scope="music_read"))
_write = Depends(rate_limit(limit=90, window_seconds=60, scope="music_write"))
_send = Depends(rate_limit(limit=20, window_seconds=60, scope="music_send"))

_PUBLIC_SHOWN = 30

router = APIRouter(prefix="/api/music", tags=["music"], route_class=DishkaRoute)


def _now() -> datetime:
    return datetime.now(UTC)


def _sent(outcome: SendOutcome, count: int) -> SendOut:
    if outcome is SendOutcome.NOT_FOUND:
        raise HTTPException(status_code=404, detail="track_not_found")
    if outcome is SendOutcome.BOT_BLOCKED:
        raise HTTPException(status_code=409, detail="bot_unreachable")
    if outcome in (SendOutcome.TRY_LATER, SendOutcome.BUSY):
        raise HTTPException(status_code=503, detail="try_later", headers={"Retry-After": "5"})
    return SendOut(status="sent", count=count)


def _detail(view: PlaylistView | None, config: AppConfig, user: User) -> PlaylistDetailOut:
    if view is None:
        raise HTTPException(status_code=404, detail="playlist_not_found")
    return PlaylistDetailOut.from_view(view, config.bot.username, user.telegram_id)


# ── Каталог ────────────────────────────────────────────────────────────────────


@router.get("/home", response_model=MusicHomeOut, dependencies=[_read])
async def home(
    music: FromDishka[MusicCatalogService],
    _user: User = Depends(get_current_user),
) -> MusicHomeOut:
    return MusicHomeOut.from_domain(await music.home())


@router.get("/tracks", response_model=list[TrackOut], dependencies=[_read])
async def list_tracks(
    music: FromDishka[MusicCatalogService],
    q: str = Query("", max_length=200),
    sort: str = Query("new", pattern="^(new|popular)$"),
    offset: int = Query(0, ge=0, le=100_000),
    limit: int = Query(30, ge=1, le=50),
    _user: User = Depends(get_current_user),
) -> list[TrackOut]:
    if q.strip():
        tracks = await music.search(q, limit, offset)
    else:
        tracks = await music.browse(sort == "popular", limit, offset)
    return tracks_out(tracks)


@router.get("/tracks/{track_id}", response_model=TrackOut, dependencies=[_read])
async def get_track(
    track_id: int,
    music: FromDishka[MusicCatalogService],
    _user: User = Depends(get_current_user),
) -> TrackOut:
    track = await music.get(track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="track_not_found")
    return TrackOut.from_domain(track)


@router.get("/collections", response_model=list[CollectionOut], dependencies=[_read])
async def collections(
    music: FromDishka[MusicCatalogService],
    _user: User = Depends(get_current_user),
) -> list[CollectionOut]:
    """Готовые плейлисты из каталога: хиты недели, новые, лучшие."""
    return [collection_out(view) for view in await music.collections(_now())]


@router.get("/collections/{key}", response_model=CollectionDetailOut, dependencies=[_read])
async def collection(
    key: str,
    music: FromDishka[MusicCatalogService],
    _user: User = Depends(get_current_user),
) -> CollectionDetailOut:
    found = get_collection(key)
    if found is None:
        raise HTTPException(status_code=404, detail="collection_not_found")
    return collection_detail(await music.collection(found, _now()))


@router.get("/tracks/{track_id}/details", response_model=TrackDetailOut, dependencies=[_read])
async def track_details(
    track_id: int,
    music: FromDishka[MusicCatalogService],
    config: FromDishka[AppConfig],
    user: User = Depends(get_current_user),
) -> TrackDetailOut:
    """Страница трека: сколько слушали, в скольких плейлистах, похожие и плейлисты с ним."""
    details = await music.details(track_id)
    if details is None:
        raise HTTPException(status_code=404, detail="track_not_found")
    return TrackDetailOut.from_domain(details, config.bot.username, user.telegram_id)


@router.get("/artists/{slug}", response_model=ArtistOut, dependencies=[_read])
async def artist(
    slug: str,
    music: FromDishka[MusicCatalogService],
    _user: User = Depends(get_current_user),
) -> ArtistOut:
    """Все песни исполнителя (по ключу, как в поиске: «Қайрат» = «Кайрат»)."""
    page = await music.artist(artist_key_from_slug(slug))
    if page is None:
        raise HTTPException(status_code=404, detail="artist_not_found")
    return ArtistOut(name=page.name, slug=artist_slug(page.name), tracks=tracks_out(page.tracks))


@router.post("/send", response_model=SendOut, dependencies=[_send])
async def send_tracks(
    body: TrackIdsIn,
    delivery: FromDishka[MusicDeliveryService],
    user: User = Depends(get_current_user),
) -> SendOut:
    """Треки в чат с ботом В ПЕРЕДАННОМ ПОРЯДКЕ — «тыңдау», как «Көру» у фильма.

    Плеер Telegram играет аудио из чата подряд, поэтому «Ойнату» плейлиста — это весь
    список одним запросом, а тап по треку внутри списка — он и всё, что после него.
    Отправляется не больше `SEND_MAX`, остальное — следующим нажатием.
    """
    ids = body.track_ids[:SEND_MAX]
    return _sent(await delivery.send_tracks(user, ids, _now()), len(ids))


@router.post("/requests", response_model=MusicRequestOut, dependencies=[_write])
async def request_track(
    body: MusicRequestIn,
    music: FromDishka[MusicCatalogService],
    user: User = Depends(get_current_user),
) -> MusicRequestOut:
    votes = await music.request(user.telegram_id, body.query, _now())
    if votes is None:
        raise HTTPException(status_code=422, detail="bad_request_query")
    return MusicRequestOut(votes=votes)


@router.get("/me", response_model=MusicMeOut, dependencies=[_read])
async def music_me(
    music: FromDishka[MusicCatalogService],
    user: User = Depends(get_current_user),
) -> MusicMeOut:
    return MusicMeOut(uploaded=await music.uploaded_by(user.telegram_id))


# ── Менің музыкам ──────────────────────────────────────────────────────────────


@router.get("/library", response_model=list[TrackOut], dependencies=[_read])
async def library(
    library: FromDishka[MusicLibraryService],
    offset: int = Query(0, ge=0, le=100_000),
    limit: int = Query(100, ge=1, le=200),
    user: User = Depends(get_current_user),
) -> list[TrackOut]:
    tracks = await library.tracks(user.telegram_id, limit, offset)
    return tracks_out(tracks)


@router.get("/library/ids", response_model=IdsOut, dependencies=[_read])
async def library_ids(
    library: FromDishka[MusicLibraryService],
    user: User = Depends(get_current_user),
) -> IdsOut:
    return IdsOut(ids=await library.ids(user.telegram_id))


@router.put("/library/{track_id}", status_code=204, dependencies=[_write])
async def save_track(
    track_id: int,
    library: FromDishka[MusicLibraryService],
    user: User = Depends(get_current_user),
) -> None:
    if not await library.save(user.telegram_id, track_id, _now()):
        raise HTTPException(status_code=404, detail="track_not_found")


@router.delete("/library/{track_id}", status_code=204, dependencies=[_write])
async def unsave_track(
    track_id: int,
    library: FromDishka[MusicLibraryService],
    user: User = Depends(get_current_user),
) -> None:
    await library.remove(user.telegram_id, track_id)


# ── Плейлисты ──────────────────────────────────────────────────────────────────


@router.get("/playlists", response_model=list[PlaylistOut], dependencies=[_read])
async def my_playlists(
    playlists: FromDishka[PlaylistService],
    config: FromDishka[AppConfig],
    user: User = Depends(get_current_user),
) -> list[PlaylistOut]:
    return [
        PlaylistOut.from_domain(p, config.bot.username, user.telegram_id)
        for p in await playlists.list_mine(user.telegram_id)
    ]


@router.post("/playlists", response_model=PlaylistOut, status_code=201, dependencies=[_write])
async def create_playlist(
    body: PlaylistIn,
    playlists: FromDishka[PlaylistService],
    config: FromDishka[AppConfig],
    user: User = Depends(get_current_user),
) -> PlaylistOut:
    playlist = await playlists.create(user.telegram_id, body.title, _now(), body.track_ids)
    if playlist is None:
        raise HTTPException(status_code=409, detail="playlist_limit")
    return PlaylistOut.from_domain(playlist, config.bot.username, user.telegram_id)


@router.get("/playlists/public", response_model=list[PlaylistOut], dependencies=[_read])
async def public_playlists(
    playlists: FromDishka[PlaylistService],
    config: FromDishka[AppConfig],
    user: User = Depends(get_current_user),
) -> list[PlaylistOut]:
    """«Тыңдаушылардың плейлистері»: открытые всем, сначала самые сохраняемые."""
    return [
        PlaylistOut.from_domain(p, config.bot.username, user.telegram_id)
        for p in await playlists.list_public(_PUBLIC_SHOWN)
    ]


@router.get("/playlists/{playlist_id}", response_model=PlaylistDetailOut, dependencies=[_read])
async def open_playlist(
    playlist_id: int,
    playlists: FromDishka[PlaylistService],
    config: FromDishka[AppConfig],
    user: User = Depends(get_current_user),
) -> PlaylistDetailOut:
    return _detail(await playlists.open(user.telegram_id, playlist_id), config, user)


@router.put("/playlists/{playlist_id}/order", status_code=204, dependencies=[_write])
async def reorder_playlist(
    playlist_id: int,
    body: TrackIdsIn,
    playlists: FromDishka[PlaylistService],
    user: User = Depends(get_current_user),
) -> None:
    if not await playlists.reorder(user.telegram_id, playlist_id, body.track_ids, _now()):
        # Плейлиста нет, он чужой или набор треков устарел — фронт перечитает плейлист.
        raise HTTPException(status_code=409, detail="playlist_changed")


@router.patch("/playlists/{playlist_id}", status_code=204, dependencies=[_write])
async def update_playlist(
    playlist_id: int,
    body: PlaylistPatch,
    playlists: FromDishka[PlaylistService],
    user: User = Depends(get_current_user),
) -> None:
    """Переименовать и/или открыть всем («Бәріне көрсету»)."""
    now = _now()
    found = True
    if body.title is not None:
        found = await playlists.rename(user.telegram_id, playlist_id, body.title, now)
    if found and body.is_public is not None:
        found = await playlists.set_public(user.telegram_id, playlist_id, body.is_public, now)
    if not found:
        raise HTTPException(status_code=404, detail="playlist_not_found")


@router.delete("/playlists/{playlist_id}", status_code=204, dependencies=[_write])
async def delete_playlist(
    playlist_id: int,
    playlists: FromDishka[PlaylistService],
    user: User = Depends(get_current_user),
) -> None:
    if not await playlists.delete(user.telegram_id, playlist_id):
        raise HTTPException(status_code=404, detail="playlist_not_found")


@router.put(
    "/playlists/{playlist_id}/tracks/{track_id}",
    response_model=PlaylistAddOut,
    dependencies=[_write],
)
async def add_to_playlist(
    playlist_id: int,
    track_id: int,
    playlists: FromDishka[PlaylistService],
    user: User = Depends(get_current_user),
) -> PlaylistAddOut:
    outcome = await playlists.add_track(user.telegram_id, playlist_id, track_id, _now())
    if outcome is None:
        raise HTTPException(status_code=404, detail="playlist_not_found")
    return PlaylistAddOut(status=outcome)


@router.delete(
    "/playlists/{playlist_id}/tracks/{track_id}", status_code=204, dependencies=[_write]
)
async def remove_from_playlist(
    playlist_id: int,
    track_id: int,
    playlists: FromDishka[PlaylistService],
    user: User = Depends(get_current_user),
) -> None:
    if not await playlists.remove_track(user.telegram_id, playlist_id, track_id, _now()):
        raise HTTPException(status_code=404, detail="playlist_not_found")


# ── Чужой плейлист по ссылке ───────────────────────────────────────────────────


@router.get("/shared/{code}", response_model=PlaylistDetailOut, dependencies=[_read])
async def shared_playlist(
    code: str,
    playlists: FromDishka[PlaylistService],
    config: FromDishka[AppConfig],
    user: User = Depends(get_current_user),
) -> PlaylistDetailOut:
    return _detail(await playlists.shared(code[:16]), config, user)


@router.post("/shared/{code}/save", response_model=PlaylistOut, dependencies=[_write])
async def save_shared(
    code: str,
    playlists: FromDishka[PlaylistService],
    config: FromDishka[AppConfig],
    user: User = Depends(get_current_user),
) -> PlaylistOut:
    playlist = await playlists.save_shared(user.telegram_id, code[:16], _now())
    if playlist is None:
        raise HTTPException(status_code=404, detail="playlist_not_found")
    return PlaylistOut.from_domain(playlist, config.bot.username, user.telegram_id)
