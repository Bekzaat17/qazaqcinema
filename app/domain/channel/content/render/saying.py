"""Рендерер `saying` — нақыл сөз: цитата курсивом в кавычках + автор.

Автор — в `source` (он же попадает в подвал как атрибуция); текст — `body_kk`. Карточка
с портретом автора идёт фото, поэтому лимит подписи — 1024: длинную цитату режем в
`frame` (с «…»), но нақыл сөз по определению короток.
"""

from __future__ import annotations

from html import escape

from app.domain.channel.content.item import CAPTION_LIMIT, MESSAGE_LIMIT, ContentItem
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.render.base import RENDERERS, RenderedPost, frame


@RENDERERS.register(ContentKind.SAYING.value)
class SayingRenderer:
    def render(self, item: ContentItem) -> RenderedPost:
        quote = escape(item.body_kk.strip())
        body = f"«<i>{quote}</i>»"
        limit = CAPTION_LIMIT if item.image_path else MESSAGE_LIMIT
        return RenderedPost(head=frame(item, body, limit))
