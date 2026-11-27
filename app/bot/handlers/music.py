"""Музыка через бота: любой слушатель присылает или пересылает аудио — оно в каталоге.

Так каталог растёт сам: музыка у людей сейчас живёт в Telegram-каналах и чатах, и
переслать её боту — одно действие. Хендлер стоит ДО `fallback`: иначе аудио в личке
ловил бы шаблон «откройте профиль».

Альбом (до 10 треков одной пересылкой) приходит отдельными сообщениями; отвечаем на
первое из них, иначе человек получил бы десять одинаковых ответов подряд.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from html import escape

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.types import Message
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.application.ports.lock import Lock
from app.application.ports.rate_limit import RateLimiter
from app.application.services.music_catalog_service import (
    IngestOutcome,
    IngestResult,
    MusicCatalogService,
)
from app.bot.keyboards.common import music_keyboard
from app.bot.security import is_admin
from app.config.settings import AppConfig
from app.domain.music.track import AudioUpload

logger = logging.getLogger(__name__)

router = Router(name="music")

# Сутки на человека: живой слушатель столько не перешлёт, а спам-скрипт упрётся.
_UPLOADS_PER_DAY = 300
_ALBUM_WINDOW_SECONDS = 120

MUSIC_GREETING = (
    "🎧 <b>QazaqMusic</b> — бәріміз бірге толтыратын музыка.\n\n"
    "• Ән тыңдаңыз, өз плейлистіңізді жинаңыз, досыңызбен бөлісіңіз.\n"
    "• Экран сөніп тұрса да тыңдау үшін — «Telegram-да тыңдау»: ән осы чатқа келеді.\n"
    "• Каталогта жоқ ән сізде бар ма? Оны осы чатқа жіберіңіз немесе кез келген "
    "каналдан қайта жіберіңіз (forward) — ол бірден бәріне ашылады."
)

_REPLIES = {
    IngestOutcome.EXISTING: "👌 Бұл ән каталогта бар — «Менің музыкам» бөліміне қостым.",
    IngestOutcome.HIDDEN: "Бұл ән каталогтан алынып тасталған, қайта қосылмайды.",
    IngestOutcome.NOT_MUSIC: "Бұл аудио тым қысқа — ән емес сияқты 🙂",
}


def _upload(message: Message) -> AudioUpload | None:
    audio = message.audio
    if audio is None:
        return None
    return AudioUpload(
        file_id=audio.file_id,
        file_unique_id=audio.file_unique_id,
        duration_sec=audio.duration,
        title=audio.title,
        performer=audio.performer,
        file_name=audio.file_name,
        file_size=audio.file_size,
        mime_type=audio.mime_type,
        cover_file_id=audio.thumbnail.file_id if audio.thumbnail else None,
    )


def _reply_text(result: IngestResult, album: bool) -> str:
    if result.outcome is IngestOutcome.ADDED and result.track is not None:
        if album:
            return (
                "✅ Әндер каталогқа қосылып жатыр — бәрі «Менің музыкам» бөлімінде болады. "
                "Рақмет! 🙌"
            )
        name = f"{escape(result.track.performer)} — {escape(result.track.title)}"
        return (
            f"✅ Каталогқа қосылды: <b>{name}</b>\n"
            "Енді оны барлығы тыңдай алады. «Менің музыкам» бөлімінде де тұр 🎧"
        )
    return _REPLIES[result.outcome]


@router.message(
    F.chat.type == ChatType.PRIVATE, F.audio, StateFilter(None),
)
@inject
async def receive_audio(
    message: Message,
    config: FromDishka[AppConfig],
    music: FromDishka[MusicCatalogService],
    limiter: FromDishka[RateLimiter],
    lock: FromDishka[Lock],
) -> None:
    upload = _upload(message)
    if upload is None or message.from_user is None:
        return
    user_id = message.from_user.id
    if not await limiter.hit(f"music_upload:{user_id}", _UPLOADS_PER_DAY, 86400):
        await message.answer("Бүгінге жеткілікті 🙂 Ертең жалғастырыңыз.")
        return
    result = await music.ingest(upload, user_id, datetime.now(UTC))
    album = message.media_group_id is not None
    if album and not await lock.acquire(
        f"music_album:{message.media_group_id}", _ALBUM_WINDOW_SECONDS
    ):
        return
    track_id = result.track.id if result.track and not album else None
    await message.answer(
        _reply_text(result, album),
        parse_mode="HTML",
        reply_markup=music_keyboard(config.bot.webapp_url, track_id),
    )


@router.message(
    F.chat.type == ChatType.PRIVATE, F.document.mime_type.startswith("audio/"), StateFilter(None),
)
async def receive_audio_document(message: Message) -> None:
    # Файлом присланный mp3 у Telegram — документ без длительности и без плеера: слушать
    # его в чате нельзя, поэтому в каталог такой не берём, а подсказываем, как переслать.
    await message.answer(
        "Бұл файл құжат ретінде келді. Әнді «Музыка» ретінде жіберіңіз немесе "
        "каналдан қайта жіберіңіз (forward) — сонда каталогқа қосамын 🎧"
    )


@router.message(Command("music"), F.chat.type == ChatType.PRIVATE)
@inject
async def music_command(message: Message, config: FromDishka[AppConfig]) -> None:
    await message.answer(
        MUSIC_GREETING, parse_mode="HTML", reply_markup=music_keyboard(config.bot.webapp_url)
    )


@router.message(Command("trackhide"))
@inject
async def hide_track(
    message: Message,
    command: CommandObject,
    config: FromDishka[AppConfig],
    music: FromDishka[MusicCatalogService],
) -> None:
    """Убрать трек из каталога по жалобе: `/trackhide <id>` (id виден в ссылке t_<id>)."""
    if message.from_user is None or not is_admin(message.from_user.id, config.bot.admin_user_ids):
        return
    raw = (command.args or "").strip().removeprefix("t_")
    if not raw.isdigit():
        await message.answer("Қолдану: /trackhide <id>")
        return
    hidden = await music.hide(int(raw))
    await message.answer("✅ Ән каталогтан алынды." if hidden else "Мұндай ән табылмады.")
