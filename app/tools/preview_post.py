"""CLI: предпросмотр постов в канале — опубликовать образцы и удалить.

    python -m app.tools.preview_post abai-01 maqal-01 zhumbaq-01 atau-01 terms-01 nakyl-01
    python -m app.tools.preview_post --delete 123,124,125

Элементы берутся ПРЯМО из `content/*.yaml` (БД не нужна, ротация не трогается, журнал не
пишется): карточки рендерятся во временную папку, пост уходит тем же публикатором и теми
же рендерерами, что и по расписанию — то есть выглядит ровно так, как будет. Кнопки квиза
в предпросмотре неактивны (элемент без id в БД → «сауалнама аяқталған»).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import tempfile
from pathlib import Path

from aiogram import Bot

from app.application.ports.channel import ChannelPost
from app.config.settings import load_config
from app.domain.channel.content.render import RENDERERS
from app.infrastructure.content.yaml_loader import load_items
from app.infrastructure.images.cards_pillow import PillowCardRenderer
from app.infrastructure.telegram.channel import AiogramChannelPublisher

_log = logging.getLogger("qazaqcinema.preview")


async def _run(slugs: list[str], delete_ids: list[int], content_dir: Path) -> int:
    config = load_config()
    if not config.bot.public_channel_id:
        _log.error("BOT_PUBLIC_CHANNEL_ID не задан — некуда постить")
        return 1
    bot = Bot(config.bot.token.get_secret_value())
    try:
        with tempfile.TemporaryDirectory() as tmp:
            publisher = AiogramChannelPublisher(bot, config.bot.public_channel_id, tmp)
            if delete_ids:
                for message_id in delete_ids:
                    ok = await publisher.delete(message_id)
                    _log.info("удалён %s: %s", message_id, ok)
                return 0
            cards = PillowCardRenderer(content_dir / "fonts")
            items = {i.slug: i for i in load_items(content_dir, Path(tmp), cards)}
            sent: list[int] = []
            for slug in slugs:
                item = items.get(slug)
                if item is None:
                    _log.error("нет элемента %s", slug)
                    continue
                post = RENDERERS.get(item.kind.value)().render(item)
                first = await publisher.publish(
                    ChannelPost(text=post.head, photo_path=item.image_path, choices=post.buttons)
                )
                if first is None:
                    _log.error("%s: не ушёл", slug)
                    continue
                sent.append(first)
                for text in post.tail:
                    tail_id = await publisher.publish(ChannelPost(text=text))
                    if tail_id is not None:
                        sent.append(tail_id)
                _log.info("%s → message_id %s (+%d)", slug, first, len(post.tail))
            ids = ",".join(map(str, sent))
            _log.info("Удалить всё: python -m app.tools.preview_post --delete %s", ids)
            return 0
    finally:
        await bot.session.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Предпросмотр постов канала")
    parser.add_argument("slugs", nargs="*", help="slug'и элементов из content/*.yaml")
    parser.add_argument("--delete", default="", help="id сообщений через запятую — удалить")
    parser.add_argument("--content", default="content")
    args = parser.parse_args()
    ids = [int(x) for x in args.delete.split(",") if x.strip()]
    if not args.slugs and not ids:
        parser.error("укажи slug'и или --delete")
    sys.exit(asyncio.run(_run(args.slugs, ids, Path(args.content))))


if __name__ == "__main__":
    main()
