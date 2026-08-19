"""Юнит-тест PillowImageProcessor: нормализация к целевому формату + отказ на битом.

Картинку генерируем в памяти (Pillow), прогоняем через normalize и проверяем, что на
выходе JPEG ровно нужного размера (центр-кроп + ресайз). Битые байты → ValueError —
именно это ловит гейт визарда /add.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from app.application.ports.images import POSTER, ImageSpec
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
