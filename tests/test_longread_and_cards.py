"""Рендерер `longread`, карточки (Pillow) и загрузчик YAML с карточками."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from app.application.ports.cards import CardRenderer
from app.application.services.content_seed_service import SeedError
from app.domain.channel.cards import DEFAULT_STYLE, CardSpec, style_for_channel
from app.domain.channel.content.item import CAPTION_LIMIT, MESSAGE_LIMIT, ContentItem
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.render import RENDERERS
from app.domain.channel.content.render.longread import LongreadRenderer
from app.infrastructure.content.yaml_loader import load_items
from app.infrastructure.di.providers import build_container
from app.infrastructure.images.cards_pillow import PillowCardRenderer
from PIL import Image

FONTS = Path(__file__).resolve().parents[1] / "content" / "fonts"


def _item(body: str, image: str | None = "channel/abai-01.jpg") -> ContentItem:
    return ContentItem(
        slug="abai-01", kind=ContentKind.LONGREAD, topic="abai", title_kk="Бірінші сөз",
        body_kk=body, source="Абай", image_path=image, image_credit="Commons",
    )


# ── longread ─────────────────────────────────────────────────────────────────


def test_longread_is_registered_in_the_renderer_registry() -> None:
    assert RENDERERS.get(ContentKind.LONGREAD.value) is LongreadRenderer


def test_short_word_fits_one_caption() -> None:
    post = LongreadRenderer().render(_item("Қысқа сөз."))
    assert post.tail == ()
    assert "<b>Бірінші сөз</b>" in post.head and "Қысқа сөз." in post.head
    assert post.head.endswith("#ҚараСөз #ҚазақшаҮйренеміз")
    assert len(post.head) <= CAPTION_LIMIT


def test_long_word_goes_caption_plus_text_messages() -> None:
    """Подпись к карточке — только шапка/название/подвал; сам текст — сообщениями следом."""
    body = "\n\n".join("Абзац " * 120 + "соңы." for _ in range(8))  # ~6 000 символов
    post = LongreadRenderer().render(_item(body))
    assert len(post.head) <= CAPTION_LIMIT
    assert "Толық мәтіні төменде" in post.head and "#ҚараСөз" in post.head
    assert len(post.tail) == 2
    assert all(len(chunk) <= MESSAGE_LIMIT for chunk in post.tail)
    assert "".join(post.tail).count("соңы.") == 8  # ничего не потеряно


def test_medium_word_without_image_is_a_single_message() -> None:
    """Без картинки лимит — 4096, и текст в 2 000 символов уходит одним сообщением."""
    post = LongreadRenderer().render(_item("Сөз. " * 400, image=None))
    assert post.tail == () and len(post.head) <= MESSAGE_LIMIT


def test_html_in_body_is_escaped() -> None:
    post = LongreadRenderer().render(_item("а < б"))
    assert "а &lt; б" in post.head


# ── карточки ─────────────────────────────────────────────────────────────────


def _portrait() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (300, 400), (120, 90, 60)).save(buf, format="PNG")
    return buf.getvalue()


def test_card_is_a_jpeg_of_the_template_size() -> None:
    spec = CardSpec(
        title="Он тоғызыншы сөз", portrait="authors/abai.jpg",
        label="Абайдың қара сөздері", subtitle="Абай Құнанбайұлы · 1845–1904",
    )
    jpeg = PillowCardRenderer(FONTS).render(spec, _portrait())
    image = Image.open(BytesIO(jpeg))
    assert image.format == "JPEG"
    assert image.size == (DEFAULT_STYLE.width, DEFAULT_STYLE.height)


def test_channel_handle_comes_from_config_not_code() -> None:
    assert style_for_channel("qazaqcinema_kz").handle == "@qazaqcinema_kz"
    assert style_for_channel("@qazaqcinema_kz").handle == "@qazaqcinema_kz"
    # Канал не настроен → подвала на карточке нет (адреса в коде домена не держим).
    assert style_for_channel("").handle == ""
    assert DEFAULT_STYLE.handle == ""


def test_card_renders_with_and_without_channel_footer() -> None:
    spec = CardSpec(title="Бірінші сөз", portrait="authors/abai.jpg")
    with_footer = PillowCardRenderer(FONTS, style_for_channel("qazaqcinema_kz"))
    without = PillowCardRenderer(FONTS)
    assert Image.open(BytesIO(with_footer.render(spec, _portrait()))).format == "JPEG"
    assert Image.open(BytesIO(without.render(spec, _portrait()))).format == "JPEG"


async def test_container_builds_card_renderer_from_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Порт `CardRenderer` собирается в composition root, хэндл приходит из env."""
    monkeypatch.setenv("BOT_PUBLIC_CHANNEL_USERNAME", "qazaqcinema_kz")
    monkeypatch.setenv("MEDIA_CONTENT_ROOT", str(FONTS.parent))
    container = build_container()
    try:
        renderer = await container.get(CardRenderer)
        assert isinstance(renderer, PillowCardRenderer)
        jpeg = renderer.render(CardSpec(title="Бірінші сөз"), None)
        assert Image.open(BytesIO(jpeg)).size == (DEFAULT_STYLE.width, DEFAULT_STYLE.height)
    finally:
        await container.close()


def test_card_rejects_broken_portrait() -> None:
    with pytest.raises(ValueError):
        PillowCardRenderer(FONTS).render(CardSpec("Т", "x.jpg"), b"not an image")


def test_very_long_title_still_renders() -> None:
    spec = CardSpec(title="Сөз " * 60, portrait="p.jpg")
    assert PillowCardRenderer(FONTS).render(spec, _portrait())


# ── YAML + карточки ──────────────────────────────────────────────────────────


class _FakeCards:
    def __init__(self) -> None:
        self.specs: list[CardSpec] = []

    def render(self, spec: CardSpec, portrait: bytes) -> bytes:
        self.specs.append(spec)
        return b"JPEG"


def _content_dir(tmp_path: Path, yaml_text: str) -> Path:
    content = tmp_path / "content"
    (content / "images" / "authors").mkdir(parents=True)
    (content / "images" / "authors" / "abai.jpg").write_bytes(b"portrait")
    (content / "abai.yaml").write_text(yaml_text, encoding="utf-8")
    return content


def test_card_entry_renders_and_writes_channel_image(tmp_path: Path) -> None:
    content = _content_dir(tmp_path, """
- slug: abai-01
  kind: longread
  topic: abai
  title: Бірінші сөз
  body: Мәтін.
  card: {portrait: authors/abai.jpg, label: Абайдың қара сөздері, subtitle: Абай}
""")
    cards = _FakeCards()
    media = tmp_path / "uploads"
    items = load_items(content, media, cards)

    assert items[0].image_path == "channel/abai-01.jpg"
    assert (media / "channel" / "abai-01.jpg").read_bytes() == b"JPEG"
    assert cards.specs[0].title == "Бірінші сөз" and cards.specs[0].label == "Абайдың қара сөздері"


def test_check_mode_renders_but_does_not_write(tmp_path: Path) -> None:
    content = _content_dir(tmp_path, """
- {slug: a, kind: longread, topic: abai, title: T, body: B, card: {portrait: authors/abai.jpg}}
""")
    media = tmp_path / "uploads"
    load_items(content, media, _FakeCards(), copy_images=False)
    assert not (media / "channel").exists()


def test_card_and_image_together_or_missing_portrait_fail(tmp_path: Path) -> None:
    content = _content_dir(tmp_path, """
- {slug: a, kind: longread, topic: abai, title: T, body: B, card: {portrait: authors/nope.jpg}}
""")
    with pytest.raises(SeedError, match="портрет"):
        load_items(content, tmp_path / "u", _FakeCards())
    (content / "abai.yaml").write_text(
        "- {slug: a, kind: longread, topic: abai, title: T, body: B, "
        "image: authors/abai.jpg, card: {portrait: authors/abai.jpg}}",
        encoding="utf-8",
    )
    with pytest.raises(SeedError, match="одно из двух"):
        load_items(content, tmp_path / "u", _FakeCards())
