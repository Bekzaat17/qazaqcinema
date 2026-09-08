"""CLI: залить контент канала из `content/*.yaml` в БД (+ картинки в том uploads).

    python -m app.tools.seed_content            # залить
    python -m app.tools.seed_content --check    # только проверить YAML, БД не трогать

Идемпотентно: upsert по `slug`, состояние ротации не сбрасывается. Через ./start.sh seed.

Каталог контента и генератор карточек берутся из контейнера (`MEDIA_CONTENT_ROOT`,
по умолчанию `content/`) — своего пути и своей сборки рендерера у CLI нет, иначе
предпросмотр и сидер рисовали бы карточки по-разному.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from app.application.ports.cards import CardRenderer
from app.application.services.content_seed_service import ContentSeedService, SeedError
from app.config.settings import AppConfig
from app.infrastructure.content.yaml_loader import load_items
from app.infrastructure.di.providers import build_container

_log = logging.getLogger("qazaqcinema.seed")


async def _run(check_only: bool) -> int:
    container = build_container()
    try:
        config = await container.get(AppConfig)
        cards = await container.get(CardRenderer)
        items = load_items(
            Path(config.media.content_root),
            Path(config.media.root),
            cards,
            copy_images=not check_only,
        )
        async with container() as request:
            seeder = await request.get(ContentSeedService)
            if check_only:
                seeder.validate(items)
                _log.info("YAML в порядке: %d элементов", len(items))
                return 0
            pool = await seeder.seed(items)
        for kind, count in sorted(pool.items()):
            _log.info("  %-12s %d", kind, count)
        return 0
    except SeedError as exc:
        _log.error("Сидер остановлен: %s", exc)
        return 1
    finally:
        await container.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Заливка контента канала")
    parser.add_argument("--check", action="store_true", help="только проверить, не писать")
    args = parser.parse_args()
    sys.exit(asyncio.run(_run(args.check)))


if __name__ == "__main__":
    main()
