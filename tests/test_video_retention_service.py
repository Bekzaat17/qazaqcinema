"""Юнит-тесты VideoRetentionService на фейках (без БД и aiogram).

Главное, что проверяем: чистка идёт ПАЧКАМИ и завершается; постоянный отказ Telegram не
ретраится, временный — ретраится с ограничением попыток; сбойная строка не зацикливает
джоб и не забивает голову очереди, вытесняя свежие выдачи.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.application.ports.telegram import DeleteOutcome
from app.application.services.video_retention_service import (
    BATCH_SIZE,
    MAX_ATTEMPTS,
    RETRY_INTERVAL,
    STALE_AFTER,
    VideoRetentionService,
)
from app.domain.entities.delivery import VideoDelivery

_NOW = datetime(2026, 7, 15, 12, tzinfo=UTC)
_OLD = _NOW - STALE_AFTER - timedelta(hours=1)


class _FakeNotifier:
    """Фейк TelegramNotifier: отдаёт заданный исход и считает вызовы."""

    def __init__(self, outcome: DeleteOutcome = DeleteOutcome.DELETED) -> None:
        self.deleted: list[tuple[int, int]] = []
        self._outcome = outcome

    async def delete_message(self, chat_id: int, message_id: int) -> DeleteOutcome:
        self.deleted.append((chat_id, message_id))
        return self._outcome


@dataclass
class _Row:
    created_at: datetime
    attempts: int = 0
    next_attempt_at: datetime | None = None


class _FakeDeliveries:
    """Фейк VideoDeliveryRepository поверх {id: _Row}; повторяет семантику list_due."""

    def __init__(self, rows: dict[int, _Row] | None = None) -> None:
        self.rows: dict[int, _Row] = rows or {}
        self.list_due_calls = 0

    async def add(self, user_id: int, chat_id: int, message_id: int) -> None:
        raise AssertionError("не используется")

    async def list_for_user(self, user_id: int) -> list[VideoDelivery]:
        return [
            VideoDelivery(user_id, 1000 + i, id=i, attempts=r.attempts)
            for i, r in sorted(self.rows.items())
        ]

    async def list_due(
        self, older_than: datetime, now: datetime, limit: int
    ) -> list[VideoDelivery]:
        self.list_due_calls += 1
        due = [
            (i, r)
            for i, r in sorted(self.rows.items())
            if r.created_at < older_than
            and (r.next_attempt_at is None or r.next_attempt_at <= now)
        ]
        return [
            VideoDelivery(chat_id=1, message_id=1000 + i, id=i, attempts=r.attempts)
            for i, r in due[:limit]
        ]

    async def delete_many(self, ids: list[int]) -> None:
        for row_id in ids:
            self.rows.pop(row_id, None)

    async def reschedule(self, ids: list[int], next_attempt_at: datetime) -> None:
        for row_id in ids:
            self.rows[row_id].attempts += 1
            self.rows[row_id].next_attempt_at = next_attempt_at


async def test_purge_stale_deletes_only_rows_older_than_cutoff() -> None:
    deliveries = _FakeDeliveries(
        {1: _Row(_OLD), 2: _Row(_NOW - timedelta(hours=1))}  # 2 — свежая, не трогать
    )
    notifier = _FakeNotifier()
    service = VideoRetentionService(deliveries, notifier)

    assert await service.purge_stale(_NOW) == 1
    assert notifier.deleted == [(1, 1001)]
    assert set(deliveries.rows) == {2}


async def test_purge_stale_walks_batches_until_drained() -> None:
    total = BATCH_SIZE * 2 + 5  # две с половиной пачки
    deliveries = _FakeDeliveries({i: _Row(_OLD) for i in range(1, total + 1)})
    notifier = _FakeNotifier()
    service = VideoRetentionService(deliveries, notifier)

    assert await service.purge_stale(_NOW) == total
    assert len(notifier.deleted) == total
    assert deliveries.list_due_calls == 3  # 100 + 100 + 5 (неполная → выход)
    assert deliveries.rows == {}


async def test_purge_stale_drops_row_on_permanent_refusal() -> None:
    """REFUSED (>48 ч / сообщения нет / блок) — повторять нечего, строку сносим."""
    deliveries = _FakeDeliveries({1: _Row(_OLD)})
    service = VideoRetentionService(deliveries, _FakeNotifier(DeleteOutcome.REFUSED))

    assert await service.purge_stale(_NOW) == 1
    assert deliveries.rows == {}


async def test_purge_stale_keeps_and_reschedules_row_on_transient_failure() -> None:
    deliveries = _FakeDeliveries({1: _Row(_OLD)})
    service = VideoRetentionService(deliveries, _FakeNotifier(DeleteOutcome.FAILED))

    await service.purge_stale(_NOW)

    assert set(deliveries.rows) == {1}  # строка ЖИВА — попробуем ещё
    assert deliveries.rows[1].attempts == 1
    assert deliveries.rows[1].next_attempt_at == _NOW + RETRY_INTERVAL


async def test_transient_failure_does_not_spin_forever() -> None:
    """Регресс: без next_attempt_at сбойная пачка возвращалась бы вечно.

    Берём РОВНО полную пачку — только тогда цикл идёт на второй заход (на неполной он
    выходит сразу и ничего не доказывает). Все строки падают с временным сбоем, то есть
    НЕ удаляются: единственное, что не даёт `while True` крутиться вечно, — их срок
    next_attempt_at в будущем, из-за которого следующий list_due вернёт пусто.
    """
    deliveries = _FakeDeliveries({i: _Row(_OLD) for i in range(1, BATCH_SIZE + 1)})
    notifier = _FakeNotifier(DeleteOutcome.FAILED)
    service = VideoRetentionService(deliveries, notifier)

    assert await service.purge_stale(_NOW) == BATCH_SIZE
    assert len(notifier.deleted) == BATCH_SIZE  # каждую тронули РОВНО раз за прогон
    assert deliveries.list_due_calls == 2       # вторая выборка пуста → выход
    assert len(deliveries.rows) == BATCH_SIZE   # строки живы, ждут следующего часа


async def test_purge_stale_gives_up_after_max_attempts() -> None:
    """Исчерпали попытки → просто удаляем из БД (дальше всё равно потолок 48 ч)."""
    deliveries = _FakeDeliveries({1: _Row(_OLD, attempts=MAX_ATTEMPTS - 1)})
    service = VideoRetentionService(deliveries, _FakeNotifier(DeleteOutcome.FAILED))

    assert await service.purge_stale(_NOW) == 1
    assert deliveries.rows == {}


async def test_stuck_row_does_not_block_fresh_ones() -> None:
    """Сбойная строка не забивает голову очереди: у неё срок в будущем, её пропускают."""
    deliveries = _FakeDeliveries(
        {1: _Row(_OLD, attempts=1, next_attempt_at=_NOW + timedelta(hours=1)), 2: _Row(_OLD)}
    )
    notifier = _FakeNotifier()
    service = VideoRetentionService(deliveries, notifier)

    assert await service.purge_stale(_NOW) == 1
    assert notifier.deleted == [(1, 1002)]  # тронули только id=2
    assert set(deliveries.rows) == {1}      # отложенная дождалась своего часа


async def test_purge_stale_no_rows() -> None:
    deliveries = _FakeDeliveries({})
    assert await VideoRetentionService(deliveries, _FakeNotifier()).purge_stale(_NOW) == 0


async def test_purge_for_user_deletes_all() -> None:
    deliveries = _FakeDeliveries({1: _Row(_NOW), 2: _Row(_NOW)})
    notifier = _FakeNotifier()
    service = VideoRetentionService(deliveries, notifier)

    assert await service.purge_for_user(42) == 2
    assert notifier.deleted == [(42, 1001), (42, 1002)]
    assert deliveries.rows == {}


async def test_purge_for_user_keeps_row_on_transient_failure() -> None:
    """Временный сбой при истечении → строку не теряем: её подберёт purge_stale в 40 ч.

    Снести её здесь = потерять единственный след, и видео осталось бы в чате навсегда.
    """
    deliveries = _FakeDeliveries({1: _Row(_NOW)})
    service = VideoRetentionService(deliveries, _FakeNotifier(DeleteOutcome.FAILED))

    assert await service.purge_for_user(42) == 0
    assert set(deliveries.rows) == {1}
