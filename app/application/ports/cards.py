"""Порт генератора карточек (DIP): спецификация + байты портрета → JPEG.

Синхронный: зовётся только сидером (CLI на этапе заполнения), не из обработчиков.
Реализация — Pillow (`infrastructure/images/cards_pillow.py`).
"""

from __future__ import annotations

from typing import Protocol

from app.domain.channel.cards import CardSpec


class CardRenderer(Protocol):
    def render(self, spec: CardSpec, portrait: bytes | None) -> bytes:
        """`portrait=None` — автор без открытого фото: вместо портрета инициал в круге.
        Битый портрет → ValueError (сидер остановится до записи)."""
        ...
