"""Stage S4: what the ROM shows and gives at each of our item locations, after Archipelago's fill.

For now (milestone 3, solo seeds), the plan is only a Map Rando item placement: our own items at the locations AP
chose, and Nothing where an item for another world landed. Milestone 5 adds the multiworld table rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from .catalog import Catalog


@dataclass(frozen=True)
class PlacedItem:
    """The item Archipelago placed at one of our locations."""
    name: str
    player: int
    game: str


@dataclass(frozen=True)
class MwPlan:
    item_placement: List[str]   # Map Rando item name per item location index, as Map Rando's patcher takes it


def plan(catalog: Catalog, placed: Sequence[PlacedItem], player: int, game: str) -> MwPlan:
    by_name = {item.name: item for item in catalog.items}
    placement = []
    for item in placed:
        own = item.player == player and item.game == game and item.name in by_name
        placement.append(by_name[item.name].rando_name if own else "Nothing")
    return MwPlan(placement)
