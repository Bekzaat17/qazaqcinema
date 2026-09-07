"""Рендерер `term_list` — атаулары: заголовок + список «термин — значение» + пояснение.

Влезает целиком (в подпись к фото — 1024, без фото — 4096) → одно сообщение. Список
длиннее подписи → фото с заголовком и подвалом первым сообщением, список — следом
(тот же приём, что у `longread`: хэштеги остаются в сообщении с картинкой).
"""

from __future__ import annotations

from html import escape

from app.domain.channel.content.item import (
    CAPTION_LIMIT,
    MESSAGE_LIMIT,
    ContentItem,
    TermList,
)
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.render.base import (
    RENDERERS,
    RenderedPost,
    compose,
    frame,
)
from app.domain.channel.content.split import split_text

_CONTINUES = "👇 Тізім төменде"


def render_terms(terms: TermList) -> str:
    lines = [f"▫️ <b>{escape(t.term)}</b> — {escape(t.meaning)}" for t in terms.items]
    if terms.note:
        lines += ["", escape(terms.note)]
    return "\n".join(lines)


@RENDERERS.register(ContentKind.TERM_LIST.value)
class TermListRenderer:
    def render(self, item: ContentItem) -> RenderedPost:
        terms = item.payload
        if not isinstance(terms, TermList):
            raise ValueError(f"{item.slug}: term_list без TermList payload")
        title = f"<b>{escape(item.title_kk.strip())}</b>" if item.title_kk.strip() else ""
        intro = escape(item.body_kk.strip())
        body = render_terms(terms)
        limit = CAPTION_LIMIT if item.image_path else MESSAGE_LIMIT

        whole = compose(item, "\n\n".join(p for p in (title, intro, body) if p))
        if len(whole) <= limit:
            return RenderedPost(head=whole)
        head = frame(item, "\n\n".join(p for p in (title, intro, _CONTINUES) if p), limit)
        return RenderedPost(head=head, tail=tuple(split_text(body, MESSAGE_LIMIT)))
