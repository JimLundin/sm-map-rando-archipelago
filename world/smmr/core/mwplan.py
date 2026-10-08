"""Stage S4: what the ROM shows and gives at each of our item locations, after Archipelago's fill.

Our own items are Map Rando's items at the locations AP chose. Where an item for another world landed, Samus gets
Map Rando's Nothing, and the ROM shows a foreign item (our fork of Map Rando, docs/specs/foreign-items.md): a
collectible item whose pickup sets the location's collected bit and shows who gets what ("ALICE - HOOKSHOT"),
marked on the map by its classification.
"""
from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, TypeAlias, TypedDict, assert_never

from .catalog import Catalog
from .logic import Classification

MESSAGE_ROW = 26                                         # characters in a row of the message box
MESSAGE_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .-?!")

ForeignClass: TypeAlias = Literal["Progression", "Useful", "Filler"]


@dataclass(frozen=True, slots=True)
class OwnItem:
    """One of our items (any player's world of our game would be an OtherWorldItem)."""
    name: str                                            # Archipelago name


@dataclass(frozen=True, slots=True)
class OtherWorldItem:
    """An item that belongs to another player."""
    name: str
    recipient: str                                       # the player's name
    classification: Classification


PlacedItem: TypeAlias = OwnItem | OtherWorldItem         # what Archipelago placed at one of our locations


# Map Rando's `Randomization.foreign_items` entry (the functional syntax: `class` is a keyword).
ForeignItem = TypedDict("ForeignItem", {"location_idx": int, "class": ForeignClass, "message": list[str]})


@dataclass(frozen=True, slots=True)
class MwPlan:
    item_placement: list[str]                            # Map Rando item name per item location index
    foreign_items: list[ForeignItem] = field(default_factory=list[ForeignItem])


def foreign_class(classification: Classification) -> ForeignClass:
    match classification:
        case Classification.PROGRESSION | Classification.PROGRESSION_SKIP_BALANCING:
            return "Progression"
        case Classification.USEFUL:
            return "Useful"
        case Classification.FILLER:
            return "Filler"
        case _:
            assert_never(classification)


def message_text(text: str) -> str:
    """Text as the message box font can show it: upper case, without accents and apostrophes, any other character
    a space."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().upper().replace("'", "")
    return " ".join("".join(c if c in MESSAGE_CHARS else " " for c in text).split())


def message(recipient: str, item: str) -> list[str]:
    """The foreign item's message: "RECIPIENT - ITEM" in one row if it fits, else the two in a row each."""
    recipient, item = message_text(recipient), message_text(item)
    row = f"{recipient} - {item}"
    if len(row) <= MESSAGE_ROW:
        return [row]
    return [recipient[:MESSAGE_ROW].rstrip(), item[:MESSAGE_ROW].rstrip()]


def plan(catalog: Catalog, placed: Sequence[PlacedItem]) -> MwPlan:
    by_name = {item.name: item for item in catalog.items}
    placement: list[str] = []
    foreign: list[ForeignItem] = []
    for index, item in enumerate(placed):
        match item:
            case OwnItem(name):
                placement.append(by_name[name].rando_name)
            case OtherWorldItem(name, recipient, classification):
                placement.append("Nothing")
                foreign.append({"location_idx": index, "class": foreign_class(classification),
                                "message": message(recipient, name)})
            case _:
                assert_never(item)
    return MwPlan(placement, foreign)
