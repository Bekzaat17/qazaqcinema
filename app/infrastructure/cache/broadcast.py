"""Redis-адаптер порта `BroadcastQueue` — надёжная очередь рассылок (Фаза 12).

Устройство (reliable queue на Redis List):
  • `broadcast:pending`      — очередь заданий (RPUSH в хвост, LMOVE из головы → FIFO);
  • `broadcast:processing`   — «в работе»: reserve атомарно (LMOVE) переносит сюда, ack
                               снимает (LREM). Упал worker до ack → задание тут → recover
                               вернёт его в pending (at-least-once);
  • `broadcast:msg:<mid>`    — payload сообщения (SET один раз на рассылку, TTL 24 ч);
                               задания хранят лишь `{mid, chat}` — не дублируем контент.

**Fail-open:** Redis недоступен → enqueue возвращает 0 (рассылка пропущена, вызывающий —
напр. /add — не падает), reserve → [], ack/recover — тихий no-op. Redis не роняет ни
добавление фильма, ни worker.

**Один consumer (важно):** очередь рассчитана на РОВНО ОДИН worker. `recover()` при старте
переносит ВСЁ из `broadcast:processing` обратно в pending — при 2+ репликах recover одного
воркера утащил бы задания, ещё выполняемые другим → двойная отправка/гонки. Масштабировать
worker горизонтально нельзя без перехода на per-consumer processing-листы или Redis Streams +
consumer group. Пропускная способность одного воркера (~лимит Telegram) для MVP достаточна.
"""

from __future__ import annotations

import json
import logging
from typing import cast
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.application.ports.broadcast import BroadcastJob, BroadcastMessage, BroadcastQueue

logger = logging.getLogger(__name__)

_PENDING = "broadcast:pending"
_PROCESSING = "broadcast:processing"
_MSG_PREFIX = "broadcast:msg:"
_MSG_TTL_SECONDS = 24 * 60 * 60


def _dump_message(message: BroadcastMessage) -> str:
    return json.dumps(
        {
            "text": message.text,
            "photo_url": message.photo_url,
            "button_text": message.button_text,
            "button_url": message.button_url,
        }
    )


def _load_message(raw: str) -> BroadcastMessage:
    data = json.loads(raw)
    return BroadcastMessage(
        text=data["text"],
        photo_url=data.get("photo_url"),
        button_text=data.get("button_text"),
        button_url=data.get("button_url"),
    )


class RedisBroadcastQueue(BroadcastQueue):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def enqueue(self, message: BroadcastMessage, recipient_ids: list[int]) -> int:
        if not recipient_ids:
            return 0
        mid = uuid4().hex
        entries = [json.dumps({"mid": mid, "chat": cid}) for cid in recipient_ids]
        try:
            # Транзакция: payload и задания появляются вместе (иначе reserve мог бы забрать
            # задание раньше, чем записан его payload).
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.set(f"{_MSG_PREFIX}{mid}", _dump_message(message), ex=_MSG_TTL_SECONDS)
                pipe.rpush(_PENDING, *entries)
                await pipe.execute()
        except RedisError:
            logger.warning("Redis broadcast queue unavailable, dropping enqueue", exc_info=True)
            return 0
        return len(recipient_ids)

    async def reserve(self, batch: int) -> list[BroadcastJob]:
        jobs: list[BroadcastJob] = []
        # Задания одной рассылки делят mid → резолвим payload ОДИН раз на mid за вызов
        # (иначе до `batch` одинаковых GET). None в кэше = payload протух/потерян.
        payloads: dict[str, BroadcastMessage | None] = {}
        try:
            for _ in range(batch):
                entry = cast(
                    "str | None",
                    await self._redis.lmove(_PENDING, _PROCESSING, src="LEFT", dest="RIGHT"),
                )
                if entry is None:
                    break  # очередь пуста
                data = json.loads(entry)
                mid = data["mid"]
                if mid not in payloads:
                    raw = cast("str | None", await self._redis.get(f"{_MSG_PREFIX}{mid}"))
                    payloads[mid] = _load_message(raw) if raw is not None else None
                message = payloads[mid]
                if message is None:
                    # payload протух/потерян → задание неотправимо, снимаем из processing.
                    await self._redis.lrem(_PROCESSING, 1, entry)
                    continue
                jobs.append(
                    BroadcastJob(chat_id=int(data["chat"]), message=message, receipt=entry)
                )
        except RedisError:
            logger.warning("Redis broadcast queue unavailable, reserve failing open", exc_info=True)
        return jobs

    async def ack(self, job: BroadcastJob) -> None:
        try:
            await self._redis.lrem(_PROCESSING, 1, job.receipt)
        except RedisError:
            logger.warning("Redis broadcast queue unavailable, skipping ack", exc_info=True)

    async def recover(self) -> int:
        moved = 0
        try:
            while True:
                entry = cast(
                    "str | None",
                    await self._redis.lmove(_PROCESSING, _PENDING, src="LEFT", dest="RIGHT"),
                )
                if entry is None:
                    break
                moved += 1
        except RedisError:
            logger.warning("Redis broadcast queue unavailable, recover failing open", exc_info=True)
        return moved
