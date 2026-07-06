"""Фоновый worker рассылок (Фаза 12) — отдельный процесс (сервис `worker` в compose).

Забирает задания из `BroadcastQueue` пачками и шлёт через Bot API. Отдельный процесс —
чтобы соблюдать глобальный лимит Telegram (~30 msg/s) в ОДНОМ месте и не блокировать
бота/API. Очередь crash-safe: `recover()` при старте возвращает незавершённые задания
(доставка at-least-once — ack идёт ПОСЛЕ отправки, упавший до ack worker пере-отправит).

Реалии Telegram (плановые): `RetryAfter` → пауза и один повтор; заблокировавшие бота
(`Forbidden`/`BadRequest` chat not found) → снимаем с рассылок, не долбим впредь.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from dishka import AsyncContainer

from app.application.ports.broadcast import BroadcastJob, BroadcastQueue
from app.application.ports.repositories import UserRepository
from app.application.ports.telegram import TelegramNotifier
from app.infrastructure.di.providers import build_container

_log = logging.getLogger("qazaqcinema.worker")

# Данные (крутить здесь). Пауза между пачками держит нас ниже глобального лимита Telegram
# (~30 msg/s). Отправки в пачке последовательны, поэтому реальный темп = BATCH_SIZE за
# (суммарная задержка отправок + SEND_INTERVAL) — заведомо ниже лимита.
BATCH_SIZE = 25
SEND_INTERVAL_SECONDS = 1.0
IDLE_SLEEP_SECONDS = 2.0

# Временные ошибки Telegram — их стоит повторить (краткий сетевой сбой / 5xx на стороне TG).
_TRANSIENT_ERRORS = (TelegramNetworkError, TelegramServerError)


async def _disable_notifications(container: AsyncContainer, chat_id: int) -> None:
    """Юзер недоступен (заблокировал бота / чат не найден) → снять с рассылок."""
    async with container() as request_container:
        users = await request_container.get(UserRepository)
        await users.set_notifications(chat_id, False)


async def _deliver(
    job: BroadcastJob, notifier: TelegramNotifier, container: AsyncContainer
) -> None:
    """Отправить одно задание, разобравшись с реалиями Telegram.

    Исключения наружу НЕ пробрасывает: ack всё равно сделает вызывающий, иначе «мёртвый»
    получатель зациклит очередь (crash до ack покрыт recover). Логика исходов:
      • успех                         → выходим;
      • флуд-лимит / сеть / 5xx       → ВРЕМЕННО: пауза и ОДИН повтор (краткий сбой не теряет
                                        сообщение); повторный временный сбой — сдаёмся;
      • Forbidden / BadRequest        → получатель заблокировал бота / чат не найден →
                                        снимаем с рассылок, не долбим (работает и на повторе);
      • прочее (TelegramAPIError)     → логируем и сдаёмся.
    """
    for attempt in (1, 2):  # попытка + один повтор на ВРЕМЕННЫХ ошибках
        last = attempt == 2
        try:
            await notifier.send_broadcast(job.chat_id, job.message)
            return
        except TelegramRetryAfter as exc:
            if last:
                _log.warning("Повторный флуд-лимит у %s, пропускаю", job.chat_id)
                return
            _log.warning("Флуд-лимит Telegram: пауза %s c", exc.retry_after)
            await asyncio.sleep(exc.retry_after + 1)
        except _TRANSIENT_ERRORS:
            if last:
                _log.warning("Повторный временный сбой у %s, пропускаю", job.chat_id)
                return
            _log.warning("Временный сбой Telegram у %s, повтор", job.chat_id)
            await asyncio.sleep(1)
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            _log.info("Получатель %s недоступен (%s) → уведомления off", job.chat_id, exc)
            await _disable_notifications(container, job.chat_id)
            return
        except TelegramAPIError:
            _log.exception("Сбой отправки рассылки %s", job.chat_id)
            return


async def _run(
    queue: BroadcastQueue, notifier: TelegramNotifier, container: AsyncContainer
) -> None:
    recovered = await queue.recover()
    if recovered:
        _log.info("Восстановлено %d незавершённых заданий рассылки", recovered)
    _log.info("Worker рассылок запущен (пачка %d / %.1f c)", BATCH_SIZE, SEND_INTERVAL_SECONDS)
    while True:
        jobs = await queue.reserve(BATCH_SIZE)
        if not jobs:
            await asyncio.sleep(IDLE_SLEEP_SECONDS)
            continue
        for job in jobs:
            await _deliver(job, notifier, container)
            await queue.ack(job)  # ПОСЛЕ отправки → at-least-once (crash до ack → recover)
        await asyncio.sleep(SEND_INTERVAL_SECONDS)  # держим глобальный лимит Telegram


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    container = build_container()
    bot = await container.get(Bot)  # APP-синглтон; закрываем его сессию на выходе
    queue = await container.get(BroadcastQueue)
    notifier = await container.get(TelegramNotifier)
    try:
        await _run(queue, notifier, container)
    finally:
        await bot.session.close()
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
