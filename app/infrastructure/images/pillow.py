"""Pillow-реализация ImageProcessor: центр-кроп до нужной пропорции + ресайз + JPEG.

`ImageOps.fit` сам делает «заполнить рамку с центр-кропом» — ровно нужная нормализация.
Pillow синхронный и CPU-bound, поэтому обработку уводим в поток (как запись постера в
`LocalPosterStorage`), чтобы не блокировать event loop.
"""

from __future__ import annotations

import asyncio
from io import BytesIO

from PIL import Image, ImageOps

from app.application.ports.images import ImageSpec


class PillowImageProcessor:
    async def normalize(self, data: bytes, spec: ImageSpec) -> bytes:
        return await asyncio.to_thread(self._process, data, spec)

    @staticmethod
    def _process(data: bytes, spec: ImageSpec) -> bytes:
        try:
            image = Image.open(BytesIO(data))
            image.load()  # форсим декодирование — ловим обрезанные/битые файлы
        except (OSError, ValueError) as exc:  # UnidentifiedImageError ⊂ OSError
            raise ValueError("не удалось декодировать изображение") from exc
        rgb = image.convert("RGB")  # убираем альфу/палитру → корректный JPEG
        fitted = ImageOps.fit(rgb, (spec.width, spec.height), method=Image.Resampling.LANCZOS)
        out = BytesIO()
        fitted.save(out, format="JPEG", quality=spec.quality, optimize=True)
        return out.getvalue()
