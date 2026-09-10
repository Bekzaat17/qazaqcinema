"""Юнит-тест PillowImageProcessor: нормализация к целевому формату + отказ на битом.

Картинку генерируем в памяти (Pillow), прогоняем через normalize и проверяем, что на
выходе файл нужного формата и ровно нужного размера (центр-кроп + ресайз). Битые байты →
ValueError — именно это ловит гейт визарда /add.

Отдельно проверяется превью: его формат (WebP) задаёт ИМЯ файла на диске, и разъехавшись
с `thumb_url`, страница получила бы `<img>` на несуществующий адрес.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from app.application.ports.images import POSTER, POSTER_THUMB, ImageSpec
from app.application.ports.storage import thumb_url
from app.infrastructure.images.pillow import PillowImageProcessor
from PIL import Image


def _png(width: int, height: int) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


async def test_normalize_poster_to_2x3_jpeg() -> None:
    out = await PillowImageProcessor().normalize(_png(1000, 1000), POSTER)
    image = Image.open(BytesIO(out))
    assert image.format == "JPEG"
    assert image.size == (POSTER.width, POSTER.height)  # 600x900 (портрет 2:3)


async def test_normalize_crops_portrait_source_to_a_landscape_spec() -> None:
    """Обработчик умеет любую пропорцию, а не только постерную.

    Спецификация здесь задаётся прямо в тесте: в приложении сейчас один формат
    (POSTER), но `normalize` обязан оставаться общим — иначе первый же новый размер
    (превью, og:image) потребовал бы правки самого адаптера.
    """
    landscape = ImageSpec(1200, 800)
    out = await PillowImageProcessor().normalize(_png(500, 900), landscape)
    image = Image.open(BytesIO(out))
    assert image.format == "JPEG"
    assert image.size == (landscape.width, landscape.height)  # 3:2 из портрета


async def test_normalize_rejects_broken_bytes() -> None:
    with pytest.raises(ValueError):
        await PillowImageProcessor().normalize(b"not-an-image", ImageSpec(10, 10))


# ── превью: формат байтов и формат имени обязаны совпадать ────────────────────
async def test_thumb_is_encoded_as_webp() -> None:
    """WebP вместо JPEG: та же картинка примерно вдвое легче, а сеток на страницах много."""
    out = await PillowImageProcessor().normalize(_png(1000, 1000), POSTER_THUMB)
    image = Image.open(BytesIO(out))

    assert image.format == "WEBP"
    assert image.size == (POSTER_THUMB.width, POSTER_THUMB.height)


async def test_thumb_is_lighter_than_the_full_copy() -> None:
    """Смысл мелкой копии — байты: если она не легче, её незачем считать и хранить."""
    processor = PillowImageProcessor()
    source = _png(1200, 1800)

    full = await processor.normalize(source, POSTER)
    thumb = await processor.normalize(source, POSTER_THUMB)

    assert len(thumb) < len(full)


def test_thumb_url_extension_follows_the_spec_format() -> None:
    """⚠️ Имя файла выводится из формата: две записи одного факта разошлись бы при смене."""
    assert thumb_url("/posters/abc.jpg") == f"/posters/abc_sm.{POSTER_THUMB.ext}"
    assert thumb_url("/posters/abc.jpg").endswith(".webp")


def test_thumb_url_of_a_bare_name_still_gets_the_extension() -> None:
    assert thumb_url("abc") == f"abc_sm.{POSTER_THUMB.ext}"


def test_jpeg_spec_keeps_the_jpg_extension() -> None:
    """Крупная копия остаётся JPEG — правило расширения не должно её задеть."""
    assert POSTER.ext == "jpg"
