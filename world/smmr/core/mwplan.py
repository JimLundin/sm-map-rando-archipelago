"""Stage S4: what the ROM shows and gives at each of our item locations, after Archipelago's fill.

Our own items are Map Rando's items at the locations AP chose. Where an item for another world landed, Samus gets
Map Rando's Nothing, and the ROM shows a foreign item (our fork of Map Rando, docs/specs/foreign-items.md): a
collectible item whose pickup sets the location's collected bit and shows who gets what ("ALICE - HOOKSHOT"),
marked on the map by its classification.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

from .catalog import Catalog
from .logic import FILLER, PROGRESSION, USEFUL

FOREIGN_CLASSES = {PROGRESSION: "Progression", USEFUL: "Useful", FILLER: "Filler"}
MESSAGE_ROW = 26                                         # characters in a row of the message box
MESSAGE_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .-?!")


def message_text(text: str) -> str:
    """Text as the message box font can show it: upper case, without accents and apostrophes, any other character
    a space."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().upper().replace("'", "")
    return " ".join("".join(c if c in MESSAGE_CHARS else " " for c in text).split())


def message(recipient: str, item: str) -> List[str]:
    """The foreign item's message: "RECIPIENT - ITEM" in one row if it fits, else the two in a row each."""
    recipient, item = message_text(recipient), message_text(item)
    row = f"{recipient} - {item}"
    if len(row) <= MESSAGE_ROW:
        return [row]
    return [recipient[:MESSAGE_ROW].rstrip(), item[:MESSAGE_ROW].rstrip()]


@dataclass(frozen=True)
class PlacedItem:
    """The item Archipelago placed at one of our locations."""
    name: str
    player: int
    game: str
    classification: str = FILLER   # core.logic's PROGRESSION, USEFUL or FILLER
    recipient: str = ""            # the name of the player it belongs to


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
            foreign.append({"location_idx": index, "class": FOREIGN_CLASSES[item.classification],
                            "message": message(item.recipient, item.name)})
    return MwPlan(placement, foreign)
