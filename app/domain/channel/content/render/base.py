"""Контракт рендерера + общий каркас поста.

`RenderedPost.head` — ПЕРВОЕ сообщение. Если у элемента есть картинка, оно уходит
подписью к фото (лимит 1024), иначе обычным текстом (4096). Рендерер знает про
картинку (`item.image_path`) и сам решает, что поместить в head, а что в `tail` —
последующие сообщения (қара сөз длиннее лимита).

HTML: всё подставляемое экранируем ЗДЕСЬ (как в `channel/post.py`) — `<` в тексте
мақала иначе сломал бы парсинг и Telegram отказал бы в отправке.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Protocol

from app.domain.channel.content.item import ContentItem
from app.domain.channel.content.topics import CHANNEL_HASHTAG, get_topic
from app.domain.registry import Registry


@dataclass(frozen=True, slots=True)
class CallbackButton:
    text: str
    data: str   # callback_data (≤64 байт по лимиту Telegram)


@dataclass(frozen=True, slots=True)
class RenderedPost:
    head: str
    tail: tuple[str, ...] = ()
    buttons: tuple[CallbackButton, ...] = ()


class ContentRenderer(Protocol):
    def render(self, item: ContentItem) -> RenderedPost: ...


RENDERERS: Registry[ContentRenderer] = Registry("content renderer")


def header(item: ContentItem) -> str:
    """Шапка: эмодзи + подпись рубрики жирным. Незнакомая тема → только заголовок элемента."""
    topic = get_topic(item.topic)
    if topic is None:
        return f"<b>{escape(item.title_kk)}</b>"
    return f"{topic.emoji} <b>{escape(topic.title_kk)}</b>"


def footer(item: ContentItem) -> str:
    """Подвал: источник курсивом, кредит картинки, хэштеги рубрики + общий тег канала.

    Хэштеги — в КАЖДОМ посте рубрик (так подписчик листает `#ҚараСөз` как ленту), и
    в конце: Telegram обрезает подпись молча, а навигация теряться не должна — поэтому
    `frame` режет ТЕКСТ, не подвал.
    """
    lines: list[str] = []
    if item.source:
        lines.append(f"<i>{escape(item.source)}</i>")
    if item.image_path and item.image_credit:
        lines.append(f"<i>📷 {escape(item.image_credit)}</i>")
    topic = get_topic(item.topic)
    tags = [topic.hashtag] if topic else []
    tags.append(CHANNEL_HASHTAG)
    lines.append(" ".join(tags))
    return "\n".join(lines)


def frame(item: ContentItem, body_html: str, limit: int) -> str:
    """Шапка → тело → подвал, всё ≤ `limit`. Не влезает — режется ТЕЛО (с «…»), не подвал."""
    head = header(item)
    foot = footer(item)
    overhead = len(head) + len(foot) + 4  # два разделителя «\n\n»
    room = limit - overhead
    body = body_html.strip()
    if len(body) > room:
        body = body[: max(room - 1, 0)].rstrip() + "…"
    return "\n\n".join(part for part in (head, body, foot) if part)
