"""Pillow-реализация ImageProcessor: центр-кроп до нужной пропорции + ресайз + кодирование.

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
        rgb = image.convert("RGB")  # убираем альфу/палитру → корректный JPEG/WebP
        fitted = ImageOps.fit(rgb, (spec.width, spec.height), method=Image.Resampling.LANCZOS)
        out = BytesIO()
        # `method=6` — самый медленный и самый плотный режим WebP-энкодера. Постер
        # кодируется один раз при заливке, а отдаётся тысячи раз: время здесь дешевле
        # байтов. Для JPEG параметр игнорируется, отдельной ветки он не стоит.
        fitted.save(out, format=spec.fmt, quality=spec.quality, optimize=True, method=6)
        return out.getvalue()
