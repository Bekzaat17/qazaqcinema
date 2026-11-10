from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter

from app.domain.boardgame.game import Catalog
from app.domain.boardgame.validation import validate_catalog


def load_board_catalog(path: Path) -> Catalog:
    catalog = TypeAdapter(Catalog).validate_json(path.read_text(encoding="utf-8"), strict=True)
    validate_catalog(catalog)
    return catalog
