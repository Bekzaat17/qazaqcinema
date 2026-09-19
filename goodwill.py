#!/usr/bin/env python3
"""Разовый скрипт: подарить дни доступа последним оплатившим и написать им в личку.

Запускать ВНУТРИ контейнера бота — там уже есть и asyncpg, и токен, и доступ к БД:

    docker exec -i qazaqcinema-bot-1 python - < goodwill.py            # показать, кого возьмёт
    docker exec -i qazaqcinema-bot-1 python - --apply < goodwill.py    # начислить и отправить

По умолчанию НИЧЕГО не делает: печатает список и новые сроки. Начисляет и пишет людям
только с `--apply`. Повторный прогон — это ещё один подарок, а не догон прошлого.

Частью приложения не является: ни импортов из `app/`, ни регистрации в `start.sh`.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import asyncpg
from aiogram import Bot

TZ = ZoneInfo("Asia/Almaty")

TEXT = (
    "🎁 Сізге сыйлық: +{days} күн\n\n"
    "Жазылым мерзіміне тағы {days} күн қостық — бізбен бірге болғаныңыз үшін рақмет.\n\n"
    "🕒 Қолжетімділік {until} дейін ашық (Алматы уақыты).\n\n"
    "Рахаттанып көріңіз! 🍿"
)

# Последние ОДОБРЕННЫЕ оплаты нужного тарифа: порядок по моменту одобрения, а не создания
# заявки — чек мог пролежать в очереди дольше следующего за ним.
SQL_RECENT = """
    SELECT p.user_id, u.username, u.expires_at
    FROM payment_requests p
    JOIN users u ON u.telegram_id = p.user_id
    WHERE p.status = 'approved' AND p.tariff = $1
    ORDER BY p.reviewed_at DESC NULLS LAST, p.id DESC
    LIMIT $2
"""


def local(moment: datetime | None) -> str:
    return f"{moment.astimezone(TZ):%d.%m.%Y %H:%M}" if moment else "нет"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Подарочные дни последним оплатившим")
    parser.add_argument("--last", type=int, default=2, help="сколько последних оплат взять")
    parser.add_argument("--tariff", default="1_day", help="тариф: 1_day или 1_month")
    parser.add_argument("--days", type=int, default=1, help="сколько дней подарить")
    parser.add_argument("--apply", action="store_true", help="без него — только показать")
    args = parser.parse_args()

    conn = await asyncpg.connect(
        host=os.environ.get("DB_HOST", "postgres"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USER", "qazaqcinema"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "qazaqcinema"),
    )
    bot = Bot(os.environ["BOT_TOKEN"])
    now = datetime.now(UTC)
    try:
        rows = await conn.fetch(SQL_RECENT, args.tariff, args.last)
        if not rows:
            print(f"Одобренных оплат по тарифу {args.tariff} нет")
            return

        seen: set[int] = set()
        for row in rows:
            user_id = row["user_id"]
            if user_id in seen:  # один человек мог платить дважды — подарок всё равно один
                continue
            seen.add(user_id)
            current = row["expires_at"]
            # Активному продлеваем от его срока, просроченному — от сейчас, иначе
            # подаренный день утёк бы в прошлое.
            base = current if current and current > now else now
            until = base + timedelta(days=args.days)
            print(f"{user_id} (@{row['username'] or '—'}): {local(current)} → {local(until)}")
            if not args.apply:
                continue
            await conn.execute(
                "UPDATE users SET expires_at = $2, status = 'active' WHERE telegram_id = $1",
                user_id,
                until,
            )
            try:
                await bot.send_message(user_id, TEXT.format(days=args.days, until=local(until)))
            except Exception as exc:
                # Дни уже начислены — сообщаем, что не дошло только письмо, чтобы повтором
                # случайно не подарить второй день.
                print(f"  ⚠️ дни начислены, но письмо не ушло: {exc}")
            else:
                print("  ✅ начислено и отправлено")

        if not args.apply:
            print("Это был показ. Начислить и отправить: тот же запуск с --apply")
    finally:
        await bot.session.close()
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
