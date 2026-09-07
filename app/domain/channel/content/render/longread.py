"""Рендерер `longread` — қара сөз: один пост, сколько бы сообщений он ни занял.

Влезает целиком (в подпись к карточке — 1024, без картинки — 4096) → одно сообщение.
Не влезает → первое сообщение: карточка + шапка + название + подвал с хэштегами; текст —
следом, кусками ≤4096 по границам абзацев (`split_text`). Подвал остаётся в первом
сообщении: это оно с картинкой, его видят в ленте, и хэштеги нужны именно там.
"""

from __future__ import annotations

from html import escape

from app.domain.channel.content.item import CAPTION_LIMIT, MESSAGE_LIMIT, ContentItem
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.render.base import (
    RENDERERS,
    RenderedPost,
    compose,
    frame,
)
from app.domain.channel.content.split import split_text

_CONTINUES = "👇 Толық мәтіні төменде"


@RENDERERS.register(ContentKind.LONGREAD.value)
class LongreadRenderer:
    def render(self, item: ContentItem) -> RenderedPost:
        title = f"<b>{escape(item.title_kk.strip())}</b>" if item.title_kk.strip() else ""
        body = escape(item.body_kk.strip())
        limit = CAPTION_LIMIT if item.image_path else MESSAGE_LIMIT

        whole = compose(item, "\n\n".join(part for part in (title, body) if part))
        if len(whole) <= limit:
            return RenderedPost(head=whole)

        head = frame(item, "\n\n".join(part for part in (title, _CONTINUES) if part), limit)
        return RenderedPost(head=head, tail=tuple(split_text(body, MESSAGE_LIMIT)))
