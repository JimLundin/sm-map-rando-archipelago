"""The world's fixed vocabulary: its items and item locations, with their Archipelago names and ids.

Built from `data/info.json`, which is the engine's `info` output (regenerate it with
`python tools/stage.py info -o world/smmr/data/info.json`). An item's Map Rando name is its key in seeds and settings;
its index in `items` is the Map Rando item id (the ROM's id too).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from collections.abc import Mapping
from typing import Any

ITEM_ID_BASE = 0x5300   # Archipelago item id = ITEM_ID_BASE + Map Rando item id
LOCATION_ID_BASE = 0x5300   # Archipelago location id = LOCATION_ID_BASE + Map Rando item location index

# Map Rando item name → (Archipelago name, unique). Unique items are one-of upgrades; the others are tanks and ammo.
ITEM_NAMES: dict[str, tuple[str, bool]] = {
    "ETank": ("Energy Tank", False),
    "Missile": ("Missile", False),
    "Super": ("Super Missile", False),
    "PowerBomb": ("Power Bomb", False),
    "Bombs": ("Bombs", True),
    "Charge": ("Charge Beam", True),
    "Ice": ("Ice Beam", True),
    "HiJump": ("Hi-Jump Boots", True),
    "SpeedBooster": ("Speed Booster", True),
    "Wave": ("Wave Beam", True),
    "Spazer": ("Spazer", True),
    "SpringBall": ("Spring Ball", True),
    "Varia": ("Varia Suit", True),
    "Gravity": ("Gravity Suit", True),
    "XRayScope": ("X-Ray Scope", True),
    "Plasma": ("Plasma Beam", True),
    "Grapple": ("Grappling Beam", True),
    "SpaceJump": ("Space Jump", True),
    "ScrewAttack": ("Screw Attack", True),
    "Morph": ("Morph Ball", True),
    "ReserveTank": ("Reserve Tank", False),
    "WallJump": ("Wall Jump Boots", True),
    "Nothing": ("Nothing", False),
    "SparkBooster": ("Spark Booster", True),
    "BlueBooster": ("Blue Booster", True),
}


@dataclass(frozen=True, slots=True)
class ItemKind:
    rando_id: int
    rando_name: str
    name: str
    unique: bool

    @property
    def ap_id(self) -> int:
        return ITEM_ID_BASE + self.rando_id


@dataclass(frozen=True, slots=True)
class ItemLocation:
    index: int
    room_id: int
    node_id: int
    room: str
    node: str
    area: str
    plm_addr: int   # ROM (PC) address of the location's item PLM

    @property
    def name(self) -> str:
        return self.room if self.node == "Item" else f"{self.room} - {self.node}"

    @property
    def ap_id(self) -> int:
        return LOCATION_ID_BASE + self.index


@dataclass(frozen=True)
class Catalog:
    version: int
    items: list[ItemKind]
    locations: list[ItemLocation]

    @staticmethod
    def from_info(info: Mapping[str, Any]) -> "Catalog":
        items: list[ItemKind] = []
        for rando_id, rando_name in enumerate(info["items"]):
            name, unique = ITEM_NAMES[rando_name]
            items.append(ItemKind(rando_id, rando_name, name, unique))
        locations = [ItemLocation(**loc) for loc in info["item_locations"]]
        return Catalog(info["version"], items, locations)

    def item(self, rando_name: str) -> ItemKind:
        return self._items_by_rando_name[rando_name]

    def location_at(self, room_id: int, node_id: int) -> ItemLocation:
        return self._locations_by_node[(room_id, node_id)]

    @cached_property
    def _items_by_rando_name(self) -> dict[str, ItemKind]:
        return {item.rando_name: item for item in self.items}

    @cached_property
    def _locations_by_node(self) -> dict[tuple[int, int], ItemLocation]:
        return {(loc.room_id, loc.node_id): loc for loc in self.locations}
