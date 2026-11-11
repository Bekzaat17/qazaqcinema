from __future__ import annotations

import re

from app.domain.boardgame.game import Catalog


def validate_catalog(catalog: Catalog) -> None:
    if (
        catalog.version < 1
        or not catalog.boards
        or not catalog.scenarios
        or not catalog.cards
        or not catalog.bots
    ):
        raise ValueError("empty_catalog")
    for ids in (
        [b.id for b in catalog.boards],
        [s.id for s in catalog.scenarios],
        [c.id for c in catalog.cards],
        [b.id for b in catalog.bots],
    ):
        if len(ids) != len(set(ids)) or any(
            not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", key) for key in ids
        ):
            raise ValueError("duplicate_or_invalid_id")
    for board in catalog.boards:
        for artwork in (
            board.illustration,
            board.thumbnail,
            board.miniature_atlas,
            board.street_atlas,
        ):
            if artwork and not re.fullmatch(r"/boardgame/art/[a-z0-9_-]+\.webp", artwork):
                raise ValueError("invalid_artwork_path")
        if board.biome not in {"almaty", "astana", "turkistan", "steppe"}:
            raise ValueError("unknown_biome")
        if len(board.tiles) < 16 or len(board.tiles) > 40 or len(board.tiles) % 4:
            raise ValueError("invalid_board_size")
        if board.tiles[0].kind != "start" or len({tile.id for tile in board.tiles}) != len(
            board.tiles
        ):
            raise ValueError("invalid_board_start")
        for color in (board.ground, board.sky, board.accent, *(tile.color for tile in board.tiles)):
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                raise ValueError("invalid_color")
        for tile in board.tiles:
            if not -1 <= tile.sprite < 8 or (tile.sprite >= 0 and not board.miniature_atlas):
                raise ValueError("invalid_tile_sprite")
            if not -1 <= tile.street_sprite < 8 or (
                tile.street_sprite >= 0 and not board.street_atlas
            ):
                raise ValueError("invalid_street_sprite")
            if tile.kind not in {
                "start",
                "property",
                "station",
                "utility",
                "tax",
                "chance",
                "community",
                "rest",
                "jail",
                "parking",
                "go_to_jail",
            }:
                raise ValueError("unknown_tile_kind")
            if (
                min(tile.price, tile.amount, tile.build_cost) < 0
                or max(tile.price, tile.amount, tile.build_cost) > 10000
            ):
                raise ValueError("invalid_tile_economy")
            if tile.kind in {"property", "station", "utility"} and (
                tile.price < 1 or not tile.rents or any(n < 1 for n in tile.rents)
            ):
                raise ValueError("invalid_rent")
            if tile.kind == "property":
                peers = [other for other in board.tiles if other.group == tile.group]
                if (
                    not tile.group
                    or len(peers) < 2
                    or tile.build_cost < 1
                    or len(tile.rents) != (6 if len(board.tiles) == 40 else 5)
                ):
                    raise ValueError("invalid_property_group")
                if any(peer.kind != "property" or peer.color != tile.color for peer in peers):
                    raise ValueError("inconsistent_group")
        for card in catalog.cards:
            if card.move is not None and (
                not 0 <= card.move < len(board.tiles)
                or board.tiles[card.move].kind in {"chance", "community"}
            ):
                raise ValueError("invalid_card_destination")
    boards = {board.id for board in catalog.boards}
    for scenario in catalog.scenarios:
        if scenario.board not in boards or not (
            scenario.round_limit == 0 or 5 <= scenario.round_limit <= 50
        ):
            raise ValueError("invalid_scenario")
        if not 300 <= scenario.starting_cash <= 10000 or not 20 <= scenario.salary <= 1000:
            raise ValueError("invalid_cash")
        if (
            not 1 <= scenario.tax_multiplier <= 5
            or not 1 <= scenario.event_multiplier <= 5
            or not 0 <= scenario.reward <= 1000
        ):
            raise ValueError("invalid_scenario_balance")
    for card in catalog.cards:
        if abs(card.amount) > 1000 or not 0 <= card.skip <= 2:
            raise ValueError("invalid_card")
    for bot in catalog.bots:
        if not 0 <= bot.reserve <= 1000 or not re.fullmatch(r"#[0-9a-fA-F]{6}", bot.color):
            raise ValueError("invalid_bot")

    for archived in catalog.legacy_catalogs:
        if archived.version >= catalog.version:
            raise ValueError("invalid_catalog_archive")
        validate_catalog(archived)
