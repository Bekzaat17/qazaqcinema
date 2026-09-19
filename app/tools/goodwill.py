"""CLI: подарить дни доступа тем, кто ждал ручной модерации чека.

    python -m app.tools.goodwill --last 2 --dry-run  # показать, кого затронет
    python -m app.tools.goodwill --last 2            # продлить и написать людям
    python -m app.tools.goodwill --user 42 --days 3  # поимённо, на три дня

Через ./start.sh goodwill. Кого именно: либо `--last N` — последние ОДОБРЕННЫЕ заявки
(`payment_requests` — единственная таблица, где оплаты всех способов лежат вместе, и
порядок там по моменту одобрения), либо `--user` поимённо, сколько угодно раз.

⚠️ Идемпотентности тут нет и быть не может: каждый прогон добавляет дни и шлёт письмо.
Поэтому сначала `--dry-run` — он печатает точный список и новые сроки, не трогая ни БД,
ни Telegram; повторный прогон без него — это ВТОРОЙ подарок, а не догон прошлого.

Начисление делает `SubscriptionService.grant_bonus` — единая точка гранта; своей
арифметики срока и своего текста письма у инструмента нет.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime, timedelta

from app.application.ports.repositories import PaymentRepository, UserRepository
from app.application.services.subscription_service import SubscriptionService
from app.domain.catalog.daily import TZ
from app.domain.subscription.expiry import extend
from app.infrastructure.di.providers import build_container

_log = logging.getLogger("qazaqcinema.goodwill")


def _local(moment: datetime | None) -> str:
    """Срок глазами человека — по Алматы (в БД он в UTC)."""
    return f"{moment.astimezone(TZ):%d.%m.%Y %H:%M}" if moment else "нет"


async def _recent_payers(payments: PaymentRepository, limit: int) -> list[int]:
    """Кто оплатил последним. Дубликаты убираем: один человек мог платить дважды подряд,
    а подарок ему полагается один — иначе `--last 2` начислило бы ему два дня."""
    requests = await payments.list_recent_approved(limit)
    seen: list[int] = []
    for request in requests:
        if request.user_id not in seen:
            seen.append(request.user_id)
    return seen


async def _run(user_ids: list[int], last: int, days: int, dry_run: bool) -> int:
    now = datetime.now(UTC)
    container = build_container()
    try:
        async with container() as request_container:
            users = await request_container.get(UserRepository)
            subscription = await request_container.get(SubscriptionService)
            targets = user_ids or await _recent_payers(
                await request_container.get(PaymentRepository), last
            )
            if not targets:
                _log.error("Некому дарить: подходящих заявок нет")
                return 1

            granted = failed = 0
            for telegram_id in targets:
                user = await users.get(telegram_id)
                if user is None:
                    _log.warning("%s — такого пользователя нет, пропускаю", telegram_id)
                    failed += 1
                    continue
                after = extend(now, timedelta(days=days), user.expires_at)
                _log.info(
                    "%s (@%s): %s → %s",
                    telegram_id,
                    user.username or "—",
                    _local(user.expires_at),
                    _local(after),
                )
                if dry_run:
                    continue
                try:
                    await subscription.grant_bonus(user, days, now)
                except Exception:
                    # Дни начисляются ДО письма, поэтому сбой тут почти всегда значит
                    # «продлили, но не написали» (бот заблокирован). Второй прогон подарит
                    # ещё день — потому и не повторяем сами, а зовём человека посмотреть.
                    _log.exception("%s — сбой, проверь вручную", telegram_id)
                    failed += 1
                    continue
                granted += 1

            if dry_run:
                _log.info("Это был --dry-run: ничего не изменено, писем не ушло")
                return 0
            _log.info("Готово: подарено %d, со сбоем %d", granted, failed)
            return 1 if failed else 0
    finally:
        await container.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Подарить дни доступа за ожидание модерации")
    who = parser.add_mutually_exclusive_group(required=True)
    who.add_argument(
        "--user", type=int, action="append", default=[], help="telegram_id (можно несколько)"
    )
    who.add_argument("--last", type=int, help="сколько последних одобренных оплат взять")
    parser.add_argument("--days", type=int, default=1, help="сколько дней подарить (по умолч. 1)")
    parser.add_argument("--dry-run", action="store_true", help="только показать, ничего не менять")
    args = parser.parse_args()
    if args.days < 1 or (args.last is not None and args.last < 1):
        parser.error("--days и --last должны быть положительными")
    sys.exit(asyncio.run(_run(args.user, args.last or 0, args.days, args.dry_run)))


if __name__ == "__main__":
    main()
