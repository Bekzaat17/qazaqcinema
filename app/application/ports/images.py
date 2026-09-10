"""Порт обработки изображений (постер, hero-баннер) — DIP.

Сервис приводит картинку к целевому формату, не зная, чем это делается (Pillow).
Спецификации — данные (как тарифы/категории): менять размер/качество здесь, без
правок сервиса. Реализация — `infrastructure/images/pillow.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ImageSpec:
    """Целевой вид картинки. `fmt` — имя формата для Pillow (`JPEG`, `WEBP`)."""

    width: int
    height: int
    quality: int = 85
    fmt: str = "JPEG"

    @property
    def ext(self) -> str:
        """Расширение файла этого формата — им и заканчивается публичный URL копии."""
        return "jpg" if self.fmt == "JPEG" else self.fmt.lower()


# Два размера одной и той же картинки фильма (широкий баннер не запрашивается — hero
# главной делает широкую поверхность из этого же постера).
POSTER = ImageSpec(600, 900)  # 2:3 — карточка фильма, hero, отправка файлом в канал
# Сетки каталога и полки: слот 110–190 px, то есть 400 px хватает даже экрану с тройной
# плотностью, а весит такая копия вдвое меньше. Качество на пару пунктов ниже: на этом
# размере разницы не видно, а байты те же самые двадцать карточек грузят разом.
#
# Формат WebP, а не JPEG: при том же визуальном качестве копия весит примерно вдвое
# меньше, а сеткой из десятков карточек ограничена вся страница целиком — и SSR-каталог,
# и полки Mini App. Фолбэк на JPEG не нужен: WebP понимают все живые браузеры и WebView
# Telegram. ⚠️ Смена формата меняет и ИМЯ файла (`thumb_url` берёт расширение отсюда),
# поэтому после правки обязателен прогон `./start.sh thumbs --force`.
POSTER_THUMB = ImageSpec(400, 600, quality=80, fmt="WEBP")


class ImageProcessor(Protocol):
    async def normalize(self, data: bytes, spec: ImageSpec) -> bytes:
        """Привести картинку к `spec` (центр-кроп до пропорции → ресайз → JPEG).

        Битый/недекодируемый вход → ValueError.
        """
        ...
