"""Stage S4: what the ROM shows and gives at each of our item locations, after Archipelago's fill.

Our own items are Map Rando's items at the locations AP chose. Where an item for another world landed, Samus gets
Map Rando's Nothing, and the ROM shows a foreign item (our fork of Map Rando, docs/specs/foreign-items.md): a
collectible item whose pickup sets the location's collected bit, marked on the map by its classification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

from .catalog import Catalog
from .logic import FILLER, PROGRESSION, USEFUL

FOREIGN_CLASSES = {PROGRESSION: "Progression", USEFUL: "Useful", FILLER: "Filler"}


@dataclass(frozen=True)
class PlacedItem:
    """The item Archipelago placed at one of our locations."""
    name: str
    player: int
    game: str
    classification: str = FILLER   # core.logic's PROGRESSION, USEFUL or FILLER


@dataclass(frozen=True)
class MwPlan:
    item_placement: List[str]   # Map Rando item name per item location index, as Map Rando's patcher takes it
    foreign_items: List[Dict[str, Any]] = field(default_factory=list)   # Map Rando's `Randomization.foreign_items`


def plan(catalog: Catalog, placed: Sequence[PlacedItem], player: int, game: str) -> MwPlan:
    by_name = {item.name: item for item in catalog.items}
    placement, foreign = [], []
    for index, item in enumerate(placed):
        if item.player == player and item.game == game and item.name in by_name:
            placement.append(by_name[item.name].rando_name)
        else:
            placement.append("Nothing")
            foreign.append({"location_idx": index, "class": FOREIGN_CLASSES[item.classification]})
    return MwPlan(placement, foreign)
