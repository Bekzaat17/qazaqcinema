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


# Единственный формат картинки фильма (решение 2026-08-19): широкий баннер больше не
# запрашивается — hero главной делает широкую поверхность из этого же постера.
POSTER = ImageSpec(600, 900)  # 2:3 — портретные карточки полок и подложка hero


class ImageProcessor(Protocol):
    async def normalize(self, data: bytes, spec: ImageSpec) -> bytes:
        """Привести картинку к `spec` (центр-кроп до пропорции → ресайз → JPEG).

        Битый/недекодируемый вход → ValueError.
        """
        ...
