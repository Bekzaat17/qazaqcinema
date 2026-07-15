"""Юнит-тесты VideoRetentionService на фейках (без БД и aiogram).

Главное, что проверяем: чистка по возрасту идёт ПАЧКАМИ и завершается, отказ Telegram
не зацикливает джоб, а срез по возрасту не трогает свежие выдачи.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.services.video_retention_service import (
    BATCH_SIZE,
    STALE_AFTER,
    VideoRetentionService,
)
from app.domain.entities.delivery import VideoDelivery

_NOW = datetime(2026, 7, 15, 12, tzinfo=UTC)


class _FakeNotifier:
    """Фейк TelegramNotifier: считает удаления; can_delete=False имитирует отказ Telegram."""

    def __init__(self, *, can_delete: bool = True) -> None:
        self.deleted: list[tuple[int, int]] = []
        self._can_delete = can_delete

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        self.deleted.append((chat_id, message_id))
        return self._can_delete


class _FakeDeliveries:
    """Фейк VideoDeliveryRepository поверх словаря {id: (delivery, created_at)}."""

    def __init__(self, rows: dict[int, datetime] | None = None) -> None:
        # id → created_at; chat/message выводим из id, чтобы не плодить параметры
        self._created: dict[int, datetime] = rows or {}
        self.list_stale_calls = 0

    async def add(self, user_id: int, chat_id: int, message_id: int) -> None:
        raise AssertionError("не используется")

    async def list_for_user(self, user_id: int) -> list[VideoDelivery]:
        return [VideoDelivery(user_id, 1000 + i, id=i) for i in sorted(self._created)]

    async def clear_for_user(self, user_id: int) -> None:
        self._created.clear()

    async def list_stale(self, older_than: datetime, limit: int) -> list[VideoDelivery]:
        self.list_stale_calls += 1
        stale = sorted(i for i, ts in self._created.items() if ts < older_than)
        return [VideoDelivery(chat_id=1, message_id=1000 + i, id=i) for i in stale[:limit]]

    async def delete_many(self, ids: list[int]) -> None:
        for row_id in ids:
            self._created.pop(row_id, None)


async def test_purge_stale_deletes_only_rows_older_than_cutoff() -> None:
    deliveries = _FakeDeliveries(
        {
            1: _NOW - STALE_AFTER - timedelta(hours=1),  # просрочена → удалить
            2: _NOW - timedelta(hours=1),                 # свежая → оставить
        }
    )
    notifier = _FakeNotifier()
    service = VideoRetentionService(deliveries, notifier)

    count = await service.purge_stale(_NOW)

    assert count == 1
    assert notifier.deleted == [(1, 1001)]


async def test_purge_stale_walks_batches_until_drained() -> None:
    # Две с половиной пачки просроченных: сервис обязан выгрести все, не таща их разом.
    total = BATCH_SIZE * 2 + 5
    old = _NOW - STALE_AFTER - timedelta(hours=1)
    deliveries = _FakeDeliveries(dict.fromkeys(range(1, total + 1), old))
    notifier = _FakeNotifier()
    service = VideoRetentionService(deliveries, notifier)

    count = await service.purge_stale(_NOW)

    assert count == total
    assert len(notifier.deleted) == total
    # 3 полных захода (100 + 100 + 5): последняя пачка неполная → цикл вышел без лишнего
    assert deliveries.list_stale_calls == 3


async def test_purge_stale_drops_rows_even_when_telegram_refuses() -> None:
    """Отказ Telegram (>48 ч / уже удалено) не должен зацикливать джоб.

    Строку всё равно убираем: иначе она вернётся следующим list_stale — и так навсегда.
    """
    old = _NOW - STALE_AFTER - timedelta(hours=1)
    deliveries = _FakeDeliveries({1: old, 2: old})
    notifier = _FakeNotifier(can_delete=False)
    service = VideoRetentionService(deliveries, notifier)

    count = await service.purge_stale(_NOW)

    assert count == 2
    assert await deliveries.list_stale(_NOW, BATCH_SIZE) == []  # строк не осталось


async def test_purge_stale_no_rows() -> None:
    deliveries = _FakeDeliveries({})
    service = VideoRetentionService(deliveries, _FakeNotifier())

    assert await service.purge_stale(_NOW) == 0


async def test_purge_for_user_deletes_all_and_clears() -> None:
    deliveries = _FakeDeliveries({1: _NOW, 2: _NOW})
    notifier = _FakeNotifier()
    service = VideoRetentionService(deliveries, notifier)

    count = await service.purge_for_user(42)

    assert count == 2
    assert notifier.deleted == [(42, 1001), (42, 1002)]
    assert await deliveries.list_stale(_NOW, BATCH_SIZE) == []
