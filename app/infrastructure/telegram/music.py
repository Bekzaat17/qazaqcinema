"""aiogram-адаптеры музыки: отправка аудио в личку, архивный канал, файлы для Mini App."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import TypeVar

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import InputMediaAudio

from app.application.ports.telegram import (
    RecipientUnreachableError,
    TelegramTemporarilyUnavailableError,
)

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

# ⚠️ Bot API не отдаёт боту файлы тяжелее 20 МБ (getFile отвечает «file is too big»).
_DOWNLOAD_LIMIT = 20 * 1024 * 1024


class AiogramAudioSender:
    """Аудио в личку без `protect_content`: музыку можно пересылать — так она и растёт."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def _call(self, chat_id: int, send: Callable[[], Awaitable[_T]]) -> _T:
        # Тот же разбор исходов, что у выдачи видео: флуд-лимит пережидаем один раз,
        # закрытый чат и временный сбой — разные исключения порта, а не 500.
        for attempt in (1, 2):
            try:
                return await send()
            except TelegramForbiddenError as exc:
                raise RecipientUnreachableError(str(exc)) from exc
            except TelegramRetryAfter as exc:
                if attempt == 2:
                    raise TelegramTemporarilyUnavailableError(str(exc)) from exc
                await asyncio.sleep(exc.retry_after + 1)
            except (TelegramNetworkError, TelegramServerError) as exc:
                logger.warning("Временный сбой отправки аудио в чат %s: %s", chat_id, exc)
                raise TelegramTemporarilyUnavailableError(str(exc)) from exc
            except TelegramBadRequest as exc:
                if "chat not found" in str(exc).lower():
                    raise RecipientUnreachableError(str(exc)) from exc
                raise
        raise TelegramTemporarilyUnavailableError("не удалось отправить аудио")

    async def send_audio(self, chat_id: int, file_id: str, caption: str) -> int:
        async def send() -> int:
            message = await self._bot.send_audio(
                chat_id, file_id, caption=caption, parse_mode="HTML"
            )
            return message.message_id

        return await self._call(chat_id, send)

    async def send_audio_album(self, chat_id: int, file_ids: Sequence[str], caption: str) -> int:
        if not file_ids:
            return 0
        if len(file_ids) == 1:
            await self.send_audio(chat_id, file_ids[0], caption)
            return 1
        # Подпись — у последнего трека альбома: Telegram показывает её под всей пачкой.
        media = [
            InputMediaAudio(
                media=file_id,
                caption=caption if index == len(file_ids) - 1 else None,
                parse_mode="HTML",
            )
            for index, file_id in enumerate(file_ids)
        ]

        async def send() -> int:
            messages = await self._bot.send_media_group(chat_id, list(media))
            return len(messages)

        return await self._call(chat_id, send)


class AiogramMusicArchive:
    """Копия трека в приватный канал-архив. Канал не настроен или сбой → `None`.

    Fail-open: архив — страховка, а не условие. Трек без копии всё равно попадает в
    каталог (file_id у бота остаётся рабочим), просто без второй точки хранения.
    """

    def __init__(self, bot: Bot, channel_id: int) -> None:
        self._bot = bot
        self._channel_id = channel_id

    async def store(self, file_id: str, caption: str) -> int | None:
        if not self._channel_id:
            return None
        try:
            message = await self._bot.send_audio(
                self._channel_id, file_id, caption=caption[:1000], disable_notification=True
            )
        except TelegramAPIError:
            logger.exception("Трек не скопирован в музыкальный архив")
            return None
        return message.message_id


class TelegramAudioFiles:
    """Кэш файлов из Telegram на диске (`<media_root>/audio/`) для плеера Mini App.

    Файл качается один раз при первом прослушивании и дальше отдаётся с диска; имя —
    `file_unique_id` (у бота он постоянный, в отличие от `file_id`). Загрузка идёт во
    временный файл с переименованием в конце: оборванная закачка не оставит
    полупустой трек, который потом отдавался бы как целый.
    """

    def __init__(self, bot: Bot, media_root: str) -> None:
        self._bot = bot
        self._root = Path(media_root) / "audio"
        self._locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def _cached(target: Path) -> bool:
        if not target.exists():
            return False
        target.touch()  # отметка «недавно слушали» для `prune`
        return True

    async def _fetch(self, file_id: str, target: Path) -> Path | None:
        if await asyncio.to_thread(self._cached, target):
            return target
        lock = self._locks.setdefault(target.name, asyncio.Lock())
        async with lock:
            if await asyncio.to_thread(self._cached, target):
                return target
            try:
                info = await self._bot.get_file(file_id)
                if info.file_size and info.file_size > _DOWNLOAD_LIMIT:
                    return None
                if info.file_path is None:
                    return None
                partial = target.with_suffix(".part")
                await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
                await self._bot.download_file(info.file_path, partial)
                await asyncio.to_thread(partial.replace, target)
            except TelegramBadRequest as exc:
                # «file is too big» и битый file_id — постоянный отказ: трек только в чат.
                logger.info("Файл %s не скачан: %s", target.name, exc)
                return None
            except (TelegramAPIError, OSError):
                logger.exception("Не удалось скачать файл %s", target.name)
                return None
            finally:
                self._locks.pop(target.name, None)
        return target

    async def audio(self, file_id: str, file_unique_id: str) -> Path | None:
        return await self._fetch(file_id, self._root / f"{file_unique_id}.audio")

    async def cover(self, file_id: str, file_unique_id: str) -> Path | None:
        return await self._fetch(file_id, self._root / "covers" / f"{file_unique_id}.jpg")

    def prune(self, max_bytes: int) -> int:
        if not self._root.exists():
            return 0
        files = [path for path in self._root.rglob("*") if path.is_file()]
        stats = [(path, path.stat()) for path in files]
        total = sum(stat.st_size for _, stat in stats)
        removed = 0
        # Сначала то, что дольше всех не слушали (mtime обновляется при каждом прослушивании).
        for path, stat in sorted(stats, key=lambda item: item[1].st_mtime):
            if total <= max_bytes:
                break
            try:
                path.unlink()
            except OSError:
                logger.warning("Не удалось удалить %s из кэша музыки", path)
                continue
            total -= stat.st_size
            removed += 1
        return removed
