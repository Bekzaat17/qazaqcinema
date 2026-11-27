"""Трек или плейлист — в чат с ботом: единственный способ слушать, как «Көру» у фильмов.

Сервер музыку не хранит и не стримит (маленький VPS, лишний трафик): файл лежит в
Telegram, бот отправляет его по `file_id`, а плеер Telegram играет в фоне и подряд — в
том числе с выключенным экраном, чего WebView Mini App на iOS не умеет.
Музыка бесплатна и пересылаемая: `protect_content` здесь нет намеренно — каждая
пересылка друзьям несёт подпись со ссылкой на бота.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum

from app.application.ports.lock import Lock
from app.application.ports.music import AudioSender, TrackRepository
from app.application.ports.repositories import UserEventRepository, UserRepository
from app.application.ports.telegram import (
    RecipientUnreachableError,
    TelegramTemporarilyUnavailableError,
)
from app.domain.analytics.events import EventKind
from app.domain.entities.user import User
from app.domain.music.track import Track

logger = logging.getLogger(__name__)

# Telegram собирает в одно сообщение-альбом не больше 10 файлов.
ALBUM_SIZE = 10
# Потолок одной отправки: плейлист на 500 треков иначе забил бы чат и упёрся бы во
# флуд-лимит Telegram на середине. Остальное человек дошлёт следующим нажатием.
SEND_MAX = 50
# Окно защиты от двойного тапа: второй запрос за это время не шлёт ничего.
_SEND_LOCK_SECONDS = 5


class SendOutcome(StrEnum):
    SENT = "sent"
    NOT_FOUND = "not_found"
    BOT_BLOCKED = "bot_blocked"  # чат с ботом закрыт — фронт просит открыть бота
    TRY_LATER = "try_later"      # флуд-лимит или сеть; чат в порядке
    BUSY = "busy"                # такая же отправка уже идёт (двойной тап)


def _caption(bot_username: str, track_id: int | None) -> str:
    target = f"t_{track_id}" if track_id is not None else "music"
    return f'🎧 <a href="https://t.me/{bot_username}?startapp={target}">QazaqMusic</a>'


class MusicDeliveryService:
    def __init__(
        self,
        tracks: TrackRepository,
        sender: AudioSender,
        users: UserRepository,
        events: UserEventRepository,
        lock: Lock,
        bot_username: str,
    ) -> None:
        self._tracks = tracks
        self._sender = sender
        self._users = users
        self._events = events
        self._lock = lock
        self._bot = bot_username.lstrip("@")

    async def send_track(self, user: User, track_id: int, now: datetime) -> SendOutcome:
        return await self.send_tracks(user, [track_id], now)

    async def send_tracks(
        self, user: User, track_ids: Sequence[int], now: datetime
    ) -> SendOutcome:
        tracks = await self._tracks.list_by_ids(list(dict.fromkeys(track_ids))[:SEND_MAX])
        if not tracks:
            return SendOutcome.NOT_FOUND
        key = f"music_send:{user.telegram_id}:{','.join(str(t.id) for t in tracks[:3])}"
        if not await self._lock.acquire(key, _SEND_LOCK_SECONDS):
            return SendOutcome.BUSY
        try:
            await self._deliver(user.telegram_id, tracks)
        except RecipientUnreachableError:
            await self._users.set_bot_started(user.telegram_id, None)
            return SendOutcome.BOT_BLOCKED
        except TelegramTemporarilyUnavailableError:
            return SendOutcome.TRY_LATER
        if not user.has_bot_chat():
            await self._users.set_bot_started(user.telegram_id, now)
        for track in tracks:
            await self.record_play(user.telegram_id, track)
        return SendOutcome.SENT

    async def _deliver(self, chat_id: int, tracks: list[Track]) -> None:
        if len(tracks) == 1:
            track = tracks[0]
            await self._sender.send_audio(
                chat_id, track.telegram_file_id, _caption(self._bot, track.id)
            )
            return
        for start in range(0, len(tracks), ALBUM_SIZE):
            chunk = tracks[start:start + ALBUM_SIZE]
            await self._sender.send_audio_album(
                chat_id, [track.telegram_file_id for track in chunk], _caption(self._bot, None)
            )

    async def record_play(self, user_id: int, track: Track) -> None:
        """Засчитать прослушивание: счётчик популярности и журнал для хит-парада."""
        if track.id is None:
            return
        await self._tracks.increment_play_count(track.id)
        await self._events.add(user_id, EventKind.TRACK_PLAY, str(track.id))
