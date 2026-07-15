"""Срок жизни выданных видео — единая точка удаления выдач из чатов.

ПОЧЕМУ ПО ВОЗРАСТУ, А НЕ ТОЛЬКО ПРИ ИСТЕЧЕНИИ ПОДПИСКИ. Telegram не даёт боту удалить
сообщение старше 48 часов (Bot API, deleteMessage). Значит схема «удалим всё, когда
кончится подписка» на месячном тарифе физически не работала: к 30-му дню почти все
выдачи были неудаляемы, и юзер оставался с коллекцией просмотренного навсегда.

Решение: держать выдачи заведомо ВНУТРИ окна. Ежечасный джоб сносит всё старше
`STALE_AFTER` (40 ч — запас ~8 ч до потолка Telegram на случай простоя джоба). Побочный
эффект — в таблице никогда нет ничего старше ~41 ч, поэтому и чистка при истечении
подписки (`purge_for_user`) всегда попадает в окно и срабатывает.

Для подписчика это не потеря: подписка жива → нажал «Көру» ещё раз и получил видео снова.

Зависит только от портов (`VideoDeliveryRepository`, `TelegramNotifier`) — про aiogram и
про то, что отказ Telegram бывает флудом, сервис не знает: это забота адаптера.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.application.ports.repositories import VideoDeliveryRepository
from app.application.ports.telegram import TelegramNotifier

logger = logging.getLogger(__name__)

# Данные (крутить здесь).
# STALE_AFTER < 48 ч (потолок Telegram) с запасом: джоб может не отработать пару часов.
STALE_AFTER = timedelta(hours=40)
# Размер пачки: столько выдач тянем из БД и разбираем за раз. Ограничивает и память,
# и длину одной транзакции — таблица растёт с трафиком, целиком её грузить незачем.
BATCH_SIZE = 100


class VideoRetentionService:
    def __init__(
        self, deliveries: VideoDeliveryRepository, notifier: TelegramNotifier
    ) -> None:
        self._deliveries = deliveries
        self._notifier = notifier

    async def purge_stale(self, now: datetime) -> int:
        """Ежечасный джоб: удалить все выдачи старше STALE_AFTER. Вернуть число разобранных.

        Идёт ПАЧКАМИ по BATCH_SIZE, пока они не кончатся — в память попадает максимум
        одна пачка, сколько бы выдач ни накопилось.

        Строки чистим НЕЗАВИСИМО от ответа Telegram — и это не небрежность, а условие
        завершения цикла: отказ (сообщения уже нет, юзер заблокировал бота, выдача старше
        48 ч из-за долгого простоя) неисправим, а оставленная строка вернулась бы
        следующим запросом и зациклила джоб навсегда. Причину отказа логирует адаптер.
        """
        cutoff = now - STALE_AFTER
        total = 0
        while True:
            batch = await self._deliveries.list_stale(cutoff, BATCH_SIZE)
            if not batch:
                break
            for delivery in batch:
                await self._notifier.delete_message(delivery.chat_id, delivery.message_id)
            await self._deliveries.delete_many([d.id for d in batch])
            total += len(batch)
            if len(batch) < BATCH_SIZE:
                break  # пачка неполная → в БД больше просроченных нет
        if total:
            logger.info("Удалено просроченных видео-выдач: %d", total)
        return total

    async def purge_for_user(self, user_id: int) -> int:
        """Снести все выдачи юзера сразу (истекла подписка). Вернуть их число.

        Не ждём 40 ч: доступ кончился — контент забираем сейчас. Выдач у одного юзера
        немного (окно 40 ч), поэтому берём списком, без пачек.
        """
        deliveries = await self._deliveries.list_for_user(user_id)
        for delivery in deliveries:
            await self._notifier.delete_message(delivery.chat_id, delivery.message_id)
        await self._deliveries.clear_for_user(user_id)
        return len(deliveries)
