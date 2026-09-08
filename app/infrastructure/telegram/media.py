"""Картинка для отправки в Telegram — всегда файлом с диска.

По ссылке картинку качает сам Telegram со своих серверов, а входящий трафик с его
диапазонов к нам режет хостер (тот же повод, что у `BOT_FORCE_POLLING`) — картинка
молча не доезжала, и пост уходил текстом. Поэтому и канал, и рассылка в личку шлют
`FSInputFile` из тома `uploads`, а путь несут ОТНОСИТЕЛЬНО медиа-корня: где корень —
знает только адаптер.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aiogram.types import FSInputFile

logger = logging.getLogger(__name__)


def photo_from_disk(media_root: Path, photo_path: str | None) -> FSInputFile | None:
    """Файл картинки внутри медиа-корня; `None` — пути нет либо файла нет на диске.

    Файла может не быть (сидер запущен без картинок, том не смонтирован) — это не
    ошибка: сообщение важнее картинки и уйдёт текстом. Но в лог это попадает, иначе
    картинки пропадали бы молча.
    """
    if photo_path is None:
        return None
    path = media_root / photo_path
    if not path.is_file():
        logger.warning("Картинка %s не найдена на диске, шлём текстом", path)
        return None
    return FSInputFile(path)
