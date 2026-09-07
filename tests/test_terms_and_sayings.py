"""Рендереры `term_list` и `saying`; карточка без портрета."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from app.domain.channel.cards import CardSpec
from app.domain.channel.content.item import CAPTION_LIMIT, ContentItem, Term, TermList
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.render import RENDERERS
from app.domain.channel.content.render.saying import SayingRenderer
from app.domain.channel.content.render.term_list import TermListRenderer
from app.infrastructure.images.cards_pillow import PillowCardRenderer
from PIL import Image

FONTS = Path(__file__).resolve().parents[1] / "content" / "fonts"


def _terms(n: int, image: str | None = "channel/t.jpg") -> ContentItem:
    return ContentItem(
        slug="t", kind=ContentKind.TERM_LIST, topic="zhylqy", title_kk="Жылқы жасы",
        body_kk="Жылқыны жасына қарай былай атайды:", image_path=image,
        payload=TermList(
            tuple(Term(f"термин{i}", "мағынасы " * 6) for i in range(n)), note="Ескерту."
        ),
    )


def test_registered() -> None:
    assert RENDERERS.get(ContentKind.TERM_LIST.value) is TermListRenderer
    assert RENDERERS.get(ContentKind.SAYING.value) is SayingRenderer


def test_short_term_list_is_one_caption_with_bold_terms() -> None:
    post = TermListRenderer().render(_terms(4))
    assert post.tail == ()
    assert "🐎 <b>Жылқы атаулары</b>" in post.head
    assert "▫️ <b>термин0</b> — мағынасы" in post.head and "Ескерту." in post.head
    assert post.head.endswith("#ЖылқыАтаулары #ҚазақшаҮйренеміз")
    assert len(post.head) <= CAPTION_LIMIT


def test_long_term_list_goes_after_the_photo() -> None:
    post = TermListRenderer().render(_terms(30))
    assert len(post.head) <= CAPTION_LIMIT and "Тізім төменде" in post.head
    assert post.tail and "термин29" in post.tail[-1]


def test_saying_is_quoted_italic_with_author_in_footer() -> None:
    item = ContentItem(
        slug="s", kind=ContentKind.SAYING, topic="nakyl", title_kk="",
        body_kk="Досыңа достық — қарыз іс, дұшпаныңа әділ бол.", source="Абай Құнанбайұлы",
        image_path="channel/s.jpg",
    )
    post = SayingRenderer().render(item)
    assert "«<i>Досыңа достық — қарыз іс, дұшпаныңа әділ бол.</i>»" in post.head
    assert "<i>Абай Құнанбайұлы</i>" in post.head and "#НақылСөз" in post.head


def test_card_without_portrait_draws_an_initial() -> None:
    spec = CardSpec(title="Тіл — жүректің айнасы", subtitle="Жүсіпбек Аймауытов · 1889–1931",
                    label="Нақыл сөз")
    jpeg = PillowCardRenderer(FONTS).render(spec, None)
    assert Image.open(BytesIO(jpeg)).size == (1280, 720)
