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
    width: int
    height: int
    quality: int = 85


# Два размера одной и той же картинки фильма (широкий баннер не запрашивается — hero
# главной делает широкую поверхность из этого же постера).
POSTER = ImageSpec(600, 900)  # 2:3 — карточка фильма, hero, отправка файлом в канал
# Сетки каталога и полки: слот 110–190 px, то есть 400 px хватает даже экрану с тройной
# плотностью, а весит такая копия вдвое меньше. Качество на пару пунктов ниже: на этом
# размере разницы не видно, а байты те же самые двадцать карточек грузят разом.
POSTER_THUMB = ImageSpec(400, 600, quality=80)


class ImageProcessor(Protocol):
    async def normalize(self, data: bytes, spec: ImageSpec) -> bytes:
        """Привести картинку к `spec` (центр-кроп до пропорции → ресайз → JPEG).

        Битый/недекодируемый вход → ValueError.
        """
        ...
