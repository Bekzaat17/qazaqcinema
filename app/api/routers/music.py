"""Музыка в Mini App: каталог, «Менің музыкам», плейлисты, прослушивание и отправка в чат.

Ответы персональные или подписанные (ссылки на прослушивание живут 12 ч), поэтому в
общий Redis-кэш каталога они не попадают — как и избранное, отдельным роутером.
Музыка бесплатна: гейта подписки здесь нет ни на одной ручке.
"""

from __future__ import annotations

from datetime import UTC, datetime

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit
from app.api.schemas.music import (
    IdsOut,
    MusicHomeOut,
    MusicRequestIn,
    MusicRequestOut,
    PlaylistAddOut,
    PlaylistDetailOut,
    PlaylistIn,
    PlaylistOut,
    SendOut,
    TrackOut,
    tracks_out,
)
from app.application.ports.music import StreamKey
from app.application.services.music_catalog_service import MusicCatalogService
from app.application.services.music_delivery_service import (
    SEND_MAX,
    MusicDeliveryService,
    SendOutcome,
)
from app.application.services.music_library_service import MusicLibraryService
from app.application.services.music_media_service import MusicMediaService
from app.application.services.playlist_service import PlaylistService, PlaylistView
from app.config.settings import AppConfig
from app.domain.entities.user import User
from app.domain.music.stream import verify_stream

# Лимиты — данные. Чтение щедрое: за одной вышкой (CGNAT) сидят сотни людей.
_read = Depends(rate_limit(limit=240, window_seconds=60, scope="music_read"))
_write = Depends(rate_limit(limit=90, window_seconds=60, scope="music_write"))
_send = Depends(rate_limit(limit=20, window_seconds=60, scope="music_send"))
_stream = Depends(rate_limit(limit=600, window_seconds=60, scope="music_stream"))

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


def _detail(
    view: PlaylistView | None, config: AppConfig, user: User, key: StreamKey
) -> PlaylistDetailOut:
    if view is None:
        raise HTTPException(status_code=404, detail="playlist_not_found")
    return PlaylistDetailOut.from_view(
        view, config.bot.username, user.telegram_id, key.value, _now()
    )


# ── Каталог ────────────────────────────────────────────────────────────────────


@router.get("/home", response_model=MusicHomeOut, dependencies=[_read])
async def home(
    music: FromDishka[MusicCatalogService],
    key: FromDishka[StreamKey],
    _user: User = Depends(get_current_user),
) -> MusicHomeOut:
    return MusicHomeOut.from_domain(await music.home(), key.value, _now())


@router.get("/tracks", response_model=list[TrackOut], dependencies=[_read])
async def list_tracks(
    music: FromDishka[MusicCatalogService],
    key: FromDishka[StreamKey],
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
    return tracks_out(tracks, key.value, _now())


@router.get("/tracks/{track_id}", response_model=TrackOut, dependencies=[_read])
async def get_track(
    track_id: int,
    music: FromDishka[MusicCatalogService],
    key: FromDishka[StreamKey],
    _user: User = Depends(get_current_user),
) -> TrackOut:
    track = await music.get(track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="track_not_found")
    return TrackOut.from_domain(track, key.value, _now())


@router.post("/tracks/{track_id}/send", response_model=SendOut, dependencies=[_send])
async def send_track(
    track_id: int,
    delivery: FromDishka[MusicDeliveryService],
    user: User = Depends(get_current_user),
) -> SendOut:
    """Трек в чат с ботом — слушать с выключенным экраном в плеере Telegram."""
    return _sent(await delivery.send_track(user, track_id, _now()), 1)


@router.post("/tracks/{track_id}/played", status_code=204, dependencies=[_write])
async def track_played(
    track_id: int,
    delivery: FromDishka[MusicDeliveryService],
    user: User = Depends(get_current_user),
) -> None:
    """Прослушивание началось в Mini App — для популярности и хит-парада недели."""
    if not await delivery.played_in_app(user.telegram_id, track_id):
        raise HTTPException(status_code=404, detail="track_not_found")


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


# ── Файлы: без авторизации заголовком (<audio>/<img> его не шлют) ───────────────


@router.get("/stream/{track_id}", dependencies=[_stream], response_model=None)
async def stream(
    track_id: int,
    media: FromDishka[MusicMediaService],
    key: FromDishka[StreamKey],
    e: int = Query(...),
    s: str = Query(..., max_length=64),
) -> FileResponse:
    if not verify_stream(key.value, track_id, e, s, _now()):
        raise HTTPException(status_code=403, detail="stream_expired")
    audio = await media.audio(track_id)
    if audio is None:
        # Трек тяжелее предела Bot API или Telegram не отдал файл: фронт предложит чат.
        raise HTTPException(status_code=404, detail="stream_unavailable")
    # FileResponse отвечает на Range — перемотка и докачка работают без своего кода.
    return FileResponse(
        audio.path, media_type=audio.mime_type,
        headers={"Cache-Control": "private, max-age=43200"},
    )


@router.get("/tracks/{track_id}/cover", dependencies=[_stream], response_model=None)
async def cover(track_id: int, media: FromDishka[MusicMediaService]) -> FileResponse:
    path = await media.cover(track_id)
    if path is None:
        raise HTTPException(status_code=404, detail="cover_not_found")
    return FileResponse(
        path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=604800"}
    )


# ── Менің музыкам ──────────────────────────────────────────────────────────────


@router.get("/library", response_model=list[TrackOut], dependencies=[_read])
async def library(
    library: FromDishka[MusicLibraryService],
    key: FromDishka[StreamKey],
    offset: int = Query(0, ge=0, le=100_000),
    limit: int = Query(100, ge=1, le=200),
    user: User = Depends(get_current_user),
) -> list[TrackOut]:
    tracks = await library.tracks(user.telegram_id, limit, offset)
    return tracks_out(tracks, key.value, _now())


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


@router.post("/library/send", response_model=SendOut, dependencies=[_send])
async def send_library(
    library: FromDishka[MusicLibraryService],
    delivery: FromDishka[MusicDeliveryService],
    user: User = Depends(get_current_user),
) -> SendOut:
    ids = [t.id for t in await library.tracks(user.telegram_id, SEND_MAX, 0) if t.id]
    outcome = await delivery.send_tracks(user, ids, _now())
    return _sent(outcome, min(len(ids), SEND_MAX))


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
    playlist = await playlists.create(user.telegram_id, body.title, _now())
    if playlist is None:
        raise HTTPException(status_code=409, detail="playlist_limit")
    return PlaylistOut.from_domain(playlist, config.bot.username, user.telegram_id)


@router.get("/playlists/{playlist_id}", response_model=PlaylistDetailOut, dependencies=[_read])
async def open_playlist(
    playlist_id: int,
    playlists: FromDishka[PlaylistService],
    config: FromDishka[AppConfig],
    key: FromDishka[StreamKey],
    user: User = Depends(get_current_user),
) -> PlaylistDetailOut:
    return _detail(await playlists.open(user.telegram_id, playlist_id), config, user, key)


@router.patch("/playlists/{playlist_id}", status_code=204, dependencies=[_write])
async def rename_playlist(
    playlist_id: int,
    body: PlaylistIn,
    playlists: FromDishka[PlaylistService],
    user: User = Depends(get_current_user),
) -> None:
    if not await playlists.rename(user.telegram_id, playlist_id, body.title, _now()):
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


@router.post("/playlists/{playlist_id}/send", response_model=SendOut, dependencies=[_send])
async def send_playlist(
    playlist_id: int,
    playlists: FromDishka[PlaylistService],
    delivery: FromDishka[MusicDeliveryService],
    user: User = Depends(get_current_user),
) -> SendOut:
    view = await playlists.open(user.telegram_id, playlist_id)
    if view is None:
        raise HTTPException(status_code=404, detail="playlist_not_found")
    return await _send_view(view, delivery, user)


async def _send_view(view: PlaylistView, delivery: MusicDeliveryService, user: User) -> SendOut:
    ids = [track.id for track in view.tracks if track.id is not None]
    outcome = await delivery.send_tracks(user, ids, _now())
    return _sent(outcome, min(len(ids), SEND_MAX))


# ── Чужой плейлист по ссылке ───────────────────────────────────────────────────


@router.get("/shared/{code}", response_model=PlaylistDetailOut, dependencies=[_read])
async def shared_playlist(
    code: str,
    playlists: FromDishka[PlaylistService],
    config: FromDishka[AppConfig],
    key: FromDishka[StreamKey],
    user: User = Depends(get_current_user),
) -> PlaylistDetailOut:
    return _detail(await playlists.shared(code[:16]), config, user, key)


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


@router.post("/shared/{code}/send", response_model=SendOut, dependencies=[_send])
async def send_shared(
    code: str,
    playlists: FromDishka[PlaylistService],
    delivery: FromDishka[MusicDeliveryService],
    user: User = Depends(get_current_user),
) -> SendOut:
    view = await playlists.shared(code[:16])
    if view is None:
        raise HTTPException(status_code=404, detail="playlist_not_found")
    return await _send_view(view, delivery, user)
