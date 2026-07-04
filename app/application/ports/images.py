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


POSTER = ImageSpec(600, 900)  # 2:3 — портретные карточки полок
HERO = ImageSpec(1200, 800)   # 3:2 — горизонтальный баннер главной (под мобилку, не 16:9)


class ImageProcessor(Protocol):
    async def normalize(self, data: bytes, spec: ImageSpec) -> bytes:
        """Привести картинку к `spec` (центр-кроп до пропорции → ресайз → JPEG).

        Битый/недекодируемый вход → ValueError.
        """
        ...
