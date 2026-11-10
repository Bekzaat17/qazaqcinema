"""Проверить набор полей и сценариев без БД и Telegram."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.config.settings import QuestConfig
from app.infrastructure.content.boardgame import load_board_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Проверка конструктора настольной игры")
    parser.add_argument("--catalog", type=Path, default=Path(QuestConfig().board_catalog))
    args = parser.parse_args()
    catalog = load_board_catalog(args.catalog)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger(__name__).info(
        "Проверено: %d полей, %d сценариев, %d карт",
        len(catalog.boards),
        len(catalog.scenarios),
        len(catalog.cards),
    )


if __name__ == "__main__":
    main()
