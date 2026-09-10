"""CLI: дорисовать мелкие копии постеров, которых ещё нет на диске.

    python -m app.tools.thumbs           # только недостающие
    python -m app.tools.thumbs --force   # пересобрать все (после смены `POSTER_THUMB`)

Через ./start.sh thumbs. Нужен, потому что постеры, залитые до появления мелких копий,
лежат на диске в одном размере, а фронт просит `<uuid>_sm.webp` у каждого. Новые фильмы
проходят через `PosterService` и приезжают с обеими копиями сразу — это разовый догон
для уже накопленного (и страховка после восстановления тома из бэкапа).

Идемпотентно: существующие копии пропускаются, оригиналы не трогаются вообще —
инструмент только ДОБАВЛЯЕТ файлы. Считает из крупной копии (оригинала загрузки уже
нет), поэтому качество на пункт хуже, чем у свежих, — на 400 px это незаметно.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from app.application.ports.images import POSTER_THUMB, ImageProcessor
from app.application.ports.storage import thumb_url
from app.config.settings import AppConfig
from app.infrastructure.di.providers import build_container

_log = logging.getLogger("qazaqcinema.thumbs")

# Тот же подкаталог, что у `LocalPosterStorage` (адаптер и инструмент ходят в одну папку).
_SUBDIR = "posters"


async def _run(force: bool) -> int:
    container = build_container()
    try:
        config = await container.get(AppConfig)
        images = await container.get(ImageProcessor)
        folder = Path(config.media.root) / _SUBDIR
        if not folder.is_dir():
            _log.error("Папки постеров нет: %s", folder)
            return 1

        # Оригиналы — крупные копии: только `.jpg` и без суффикса мелкой. Второе условие
        # нужно для копий, оставшихся от прежнего формата превью: пересчитывать превью
        # из превью нельзя.
        originals = [p for p in sorted(folder.glob("*.jpg")) if not p.stem.endswith("_sm")]

        made = skipped = failed = 0
        for source in originals:
            target = folder / thumb_url(source.name)
            if target.exists() and not force:
                skipped += 1
                continue
            try:
                small = await images.normalize(source.read_bytes(), POSTER_THUMB)
            except (OSError, ValueError):
                # Битый или нечитаемый файл — не повод ронять прогон: остальные нужнее.
                _log.warning("Не смог пересчитать %s", source.name, exc_info=True)
                failed += 1
                continue
            target.write_bytes(small)
            made += 1

        _log.info("Готово: создано %d, пропущено %d, с ошибкой %d", made, skipped, failed)
        return 1 if failed else 0
    finally:
        await container.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Мелкие копии постеров")
    parser.add_argument("--force", action="store_true", help="пересобрать даже существующие")
    args = parser.parse_args()
    sys.exit(asyncio.run(_run(args.force)))


if __name__ == "__main__":
    main()
