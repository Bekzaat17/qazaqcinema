"""Срок жизни выданных видео — единая точка удаления выдач из чатов.

ПОЧЕМУ ПО ВОЗРАСТУ, А НЕ ТОЛЬКО ПРИ ИСТЕЧЕНИИ ПОДПИСКИ. Telegram не даёт боту удалить
сообщение старше 48 часов (Bot API, deleteMessage). Значит схема «удалим всё, когда
кончится подписка» на месячном тарифе физически не работала: к 30-му дню почти все
выдачи были неудаляемы, и юзер оставался с коллекцией просмотренного навсегда.

Решение: держать выдачи заведомо ВНУТРИ окна. Ежечасный джоб сносит всё старше
`STALE_AFTER` (40 ч). Побочный эффект — в таблице никогда нет ничего старше ~41 ч,
поэтому и чистка при истечении подписки (`purge_for_user`) всегда попадает в окно.

Для подписчика это не потеря: подписка жива → нажал «Көру» ещё раз и получил видео снова.

РЕТРАИ. Смотрим на исход (`DeleteOutcome`), а не на «вызвали и ладно»:
  • DELETED / REFUSED  → строку сносим. REFUSED постоянный (>48 ч, сообщения нет, бот
    заблокирован) — повторять нечего.
  • FAILED (сеть/5xx)  → строку ОСТАВЛЯЕМ, `attempts += 1`, срок следующей попытки
    `+RETRY_INTERVAL`. Исчерпали `MAX_ATTEMPTS` → сносим (дальше всё равно 48 ч).

Почему интервал РОВНЫЙ, а не растущий: после 40 ч до потолка Telegram остаётся жёсткое
окно в 8 часов. Экспонента растянула бы попытки и сожгла окно; в фиксированном окне
надо наоборот — выжать максимум попыток. Часовой ретрай даёт их 6 внутри 8 ч, и сам
джоб (раз в час) уже является этим циклом — отдельная очередь не нужна.

Зависит только от портов — про aiogram сервис не знает: классификация ошибки в адаптере.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.application.ports.repositories import VideoDeliveryRepository
from app.application.ports.telegram import DeleteOutcome, TelegramNotifier

logger = logging.getLogger(__name__)

# Данные (крутить здесь).
# STALE_AFTER < 48 ч (потолок Telegram) с запасом: джоб может не отработать пару часов.
STALE_AFTER = timedelta(hours=40)
# Размер пачки: столько выдач тянем из БД за раз. Это лимит ОДНОГО запроса (память и
# длина транзакции), а не потолок работы за прогон — цикл идёт, пока пачки не кончатся.
BATCH_SIZE = 100
# Ретрай временного сбоя. 6 попыток × 1 ч ≈ 6 ч — влезает в окно 40→48 ч.
RETRY_INTERVAL = timedelta(hours=1)
MAX_ATTEMPTS = 6


class VideoRetentionService:
    def __init__(
        self, deliveries: VideoDeliveryRepository, notifier: TelegramNotifier
    ) -> None:
        self._deliveries = deliveries
        self._notifier = notifier

    async def purge_stale(self, now: datetime) -> int:
        """Ежечасный джоб: удалить выдачи старше STALE_AFTER. Вернуть число разобранных.

        Идёт ПАЧКАМИ по BATCH_SIZE, пока они не кончатся — в память попадает максимум одна
        пачка, сколько бы выдач ни накопилось.

        Цикл гарантированно движется: каждая взятая строка либо удаляется, либо получает
        `next_attempt_at` в будущем и выпадает из `list_due`. Без этого сбойная пачка
        возвращалась бы тем же запросом снова и снова — вечный цикл и забитая голова
        очереди, из-за которой свежие выдачи никогда не дошли бы до удаления.
        """
        cutoff = now - STALE_AFTER
        next_try = now + RETRY_INTERVAL
        total = 0
        while True:
            batch = await self._deliveries.list_due(cutoff, now, BATCH_SIZE)
            if not batch:
                break
            drop: list[int] = []
            retry: list[int] = []
            for delivery in batch:
                outcome = await self._notifier.delete_message(
                    delivery.chat_id, delivery.message_id
                )
                if outcome is DeleteOutcome.FAILED and delivery.attempts + 1 < MAX_ATTEMPTS:
                    retry.append(delivery.id)
                else:
                    # DELETED, REFUSED (постоянный) или попытки исчерпаны → строке конец.
                    drop.append(delivery.id)
            await self._deliveries.delete_many(drop)
            await self._deliveries.reschedule(retry, next_try)
            total += len(batch)
            if len(batch) < BATCH_SIZE:
                break  # пачка неполная → готовых к попытке строк в БД больше нет
        if total:
            logger.info("Разобрано просроченных видео-выдач: %d", total)
        return total

    async def purge_for_user(self, user_id: int) -> int:
        """Снести выдачи юзера сразу (истекла подписка). Вернуть число удалённых строк.

        Не ждём 40 ч: доступ кончился — контент забираем сейчас. Выдач у одного юзера
        немного (окно 40 ч), поэтому берём списком, без пачек.

        Строки, где Telegram дал ВРЕМЕННЫЙ сбой, НЕ трогаем: их подберёт ежечасный
        `purge_stale`, когда выдаче стукнет 40 ч. Снести их здесь значило бы потерять
        единственный след — видео осталось бы в чате навсегда.
        """
        deliveries = await self._deliveries.list_for_user(user_id)
        drop: list[int] = []
        for delivery in deliveries:
            outcome = await self._notifier.delete_message(
                delivery.chat_id, delivery.message_id
            )
            if outcome is not DeleteOutcome.FAILED:
                drop.append(delivery.id)
        await self._deliveries.delete_many(drop)
        return len(drop)
