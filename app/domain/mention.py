"""Ссылка на пользователя для админских карточек (чек об оплате, обращение в поддержку).

Зачем функция, а не `f"@{username}"` по месту: карточек две (чек и поддержка), они
живут в РАЗНЫХ слоях (`application/services/support_service.py` и адаптер
`infrastructure/telegram/notifier.py`) — общая чистая функция держит их одинаковыми.

Почему ссылка, а не голый `@nick`: голый хэндл Telegram подсвечивает сам, но лишь когда
username есть; без него админу оставался числовой id, по которому в один тап не написать.
Ссылка кликабельна ВСЕГДА:
  • есть username → `https://t.me/<nick>` — публичный адрес, работает у любого клиента;
  • нет username → `tg://user?id=<id>` — упоминание по id (Telegram открывает его, если
    юзер боту знаком: он к нам приходит из Mini App этого же бота).
Требует `parse_mode="HTML"` на отправке — поэтому подставляемые данные экранируем.
"""

from __future__ import annotations

from html import escape


def mention_html(telegram_id: int, username: str | None) -> str:
    """`<a>`-ссылка на юзера: подпись — `@nick` (или `id N`), адрес — чат с ним."""
    if username:
        nick = username.lstrip("@")
        return f'<a href="https://t.me/{escape(nick)}">@{escape(nick)}</a>'
    return f'<a href="tg://user?id={telegram_id}">id {telegram_id}</a>'
