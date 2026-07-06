"""Порт очереди рассылок (DIP) — Фаза 12.

Рассылка по многим получателям не может идти синхронно в хендлере: Telegram лимитирует
~30 msg/s, аудитория растёт, а процесс может упасть на середине. Поэтому — очередь:
`enqueue` кладёт задания, отдельный worker (`app/worker.py`) их `reserve`/`ack` пачками.

**Crash-safe (reliable queue):** `reserve` не удаляет задания, а атомарно переносит их в
processing-лист; `ack` снимает подтверждённое. Упавший до `ack` worker при рестарте зовёт
`recover` → незавершённые возвращаются в очередь (at-least-once: лучше повтор, чем потеря).

Реализация — `infrastructure/cache/broadcast.py` (Redis List + processing-List, fail-open).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BroadcastMessage:
    """Контент одной рассылки (шлётся многим). Presentation-agnostic — как отправлять,
    решает адаптер нотификатора."""

    text: str
    photo_url: str | None = None    # абсолютный URL постера; None → текстом
    button_text: str | None = None  # подпись inline-кнопки; None → без кнопки
    button_url: str | None = None   # URL Web App для кнопки (открывается в личке с ботом)


@dataclass(frozen=True, slots=True)
class BroadcastJob:
    """Одно задание: кому (`chat_id`) и что (`message`). `receipt` — непрозрачный токен
    для `ack` (адаптеру нужно снять именно эту запись из processing-листа)."""

    chat_id: int
    message: BroadcastMessage
    receipt: str


class BroadcastQueue(Protocol):
    async def enqueue(self, message: BroadcastMessage, recipient_ids: list[int]) -> int:
        """Поставить рассылку `message` всем `recipient_ids`. Вернуть число поставленных.

        Fail-open: хранилище недоступно → 0 (рассылка пропущена, но вызывающий — напр.
        /add — не падает).
        """
        ...

    async def reserve(self, batch: int) -> list[BroadcastJob]:
        """Атомарно забрать до `batch` заданий (перенести в processing до `ack`)."""
        ...

    async def ack(self, job: BroadcastJob) -> None:
        """Подтвердить доставку — снять задание из processing (больше не повторится)."""
        ...

    async def recover(self) -> int:
        """Вернуть «зависшие» (reserved, но не acked — напр. worker упал) задания в очередь.

        Зовётся при старте worker'а. Вернуть число восстановленных.
        """
        ...
