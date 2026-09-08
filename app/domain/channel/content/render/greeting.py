"""Рендерер `greeting` — поздравление с праздником.

Шапка — название праздника из `title_kk` («Наурыз мейрамы құтты болсын!»), а не подпись
рубрики: рубрика у всех поздравлений одна и в заголовке была бы бесполезна. Тело —
2–4 строки из `body_kk`, подвал — как у всех форм (кредит картинки + хэштеги).

Кнопок нет: пост с inline-клавиатурой Telegram не пересылает в группу обсуждений, и под
ним не появляются «Комментарии» — а праздник ровно тот случай, когда люди поздравляют
друг друга сами.
"""

from __future__ import annotations

from html import escape

from app.domain.channel.content.item import CAPTION_LIMIT, MESSAGE_LIMIT, ContentItem
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.render.base import RENDERERS, RenderedPost, frame
from app.domain.channel.content.topics import get_topic


@RENDERERS.register(ContentKind.GREETING.value)
class GreetingRenderer:
    def render(self, item: ContentItem) -> RenderedPost:
        topic = get_topic(item.topic)
        emoji = f"{topic.emoji} " if topic else ""
        head = f"{emoji}<b>{escape(item.title_kk)}</b>"
        limit = CAPTION_LIMIT if item.image_path else MESSAGE_LIMIT
        return RenderedPost(head=frame(item, escape(item.body_kk.strip()), limit, head=head))
