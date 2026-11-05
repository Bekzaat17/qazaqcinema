"""Ссылка на пользователя для админских карточек (чек об оплате, обращение в поддержку).

Зачем функция, а не `f"@{username}"` по месту: карточек две (чек и поддержка), они
живут в РАЗНЫХ слоях (`application/services/support_service.py` и адаптер
`infrastructure/telegram/notifier.py`) — общая чистая функция держит их одинаковыми.

Почему ссылка, а не голый `@nick`: голый хэндл Telegram подсвечивает сам, но лишь когда
username есть; без него админу оставался числовой id, по которому в один тап не написать.
Адрес выбирается по наличию username:
  • есть username → `https://t.me/<nick>` — публичный адрес, работает у любого клиента;
  • нет username → `tg://user?id=<id>` — упоминание по id; открытие зависит от настроек
    приватности пользователя и его взаимодействия с ботом.
Требует `parse_mode="HTML"` на отправке — поэтому подставляемые данные экранируем.
"""

from __future__ import annotations

from html import escape


def user_url(telegram_id: int, username: str | None) -> str:
    """Адрес пользователя; открытие по ID зависит от его настроек приватности."""
    if username:
        return f"https://t.me/{username.lstrip('@')}"
    return f"tg://user?id={telegram_id}"


def mention_html(telegram_id: int, username: str | None) -> str:
    """`<a>`-ссылка на юзера: подпись — `@nick` (или `id N`), адрес — чат с ним."""
    label = f"@{username.lstrip('@')}" if username else f"id {telegram_id}"
    return f'<a href="{escape(user_url(telegram_id, username))}">{escape(label)}</a>'
