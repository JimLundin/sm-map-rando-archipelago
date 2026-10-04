from __future__ import annotations

from typing import Dict, List, NamedTuple

ITEMS_START_ID = 87000


class MapRandoItemData(NamedTuple):
    rando_name: str     # name used by Map Rando (its `Item` enum), also used in settings JSON
    name: str           # Archipelago item name
    unique: bool        # unique upgrade (not ammo/tank)


# In the order of Map Rando's `Item` enum: the index is the item id used by Map Rando and by the AP basepatch.
ITEM_DATA: List[MapRandoItemData] = [
    MapRandoItemData("ETank", "Energy Tank", False),
    MapRandoItemData("Missile", "Missile", False),
    MapRandoItemData("Super", "Super Missile", False),
    MapRandoItemData("PowerBomb", "Power Bomb", False),
    MapRandoItemData("Bombs", "Bombs", True),
    MapRandoItemData("Charge", "Charge Beam", True),
    MapRandoItemData("Ice", "Ice Beam", True),
    MapRandoItemData("HiJump", "Hi-Jump Boots", True),
    MapRandoItemData("SpeedBooster", "Speed Booster", True),
    MapRandoItemData("Wave", "Wave Beam", True),
    MapRandoItemData("Spazer", "Spazer", True),
    MapRandoItemData("SpringBall", "Spring Ball", True),
    MapRandoItemData("Varia", "Varia Suit", True),
    MapRandoItemData("Gravity", "Gravity Suit", True),
    MapRandoItemData("XRayScope", "X-Ray Scope", True),
    MapRandoItemData("Plasma", "Plasma Beam", True),
    MapRandoItemData("Grapple", "Grappling Beam", True),
    MapRandoItemData("SpaceJump", "Space Jump", True),
    MapRandoItemData("ScrewAttack", "Screw Attack", True),
    MapRandoItemData("Morph", "Morph Ball", True),
    MapRandoItemData("ReserveTank", "Reserve Tank", False),
    MapRandoItemData("WallJump", "Wall Jump Boots", True),
    MapRandoItemData("Nothing", "Nothing", False),
    MapRandoItemData("SparkBooster", "Spark Booster", True),
    MapRandoItemData("BlueBooster", "Blue Booster", True),
]

NOTHING_INDEX = 22
# First item id (in the AP basepatch's item numbering) used to show names of off-world items.
OFFWORLD_ITEM_FIRST_ID = len(ITEM_DATA)

item_name_to_id: Dict[str, int] = {d.name: ITEMS_START_ID + i for i, d in enumerate(ITEM_DATA)}
rando_name_to_index: Dict[str, int] = {d.rando_name: i for i, d in enumerate(ITEM_DATA)}
rando_name_to_name: Dict[str, str] = {d.rando_name: d.name for d in ITEM_DATA}
name_to_rando_name: Dict[str, str] = {d.name: d.rando_name for d in ITEM_DATA}

item_name_groups = {
    "Beams": {"Charge Beam", "Ice Beam", "Wave Beam", "Spazer", "Plasma Beam"},
    "Suits": {"Varia Suit", "Gravity Suit"},
    "Boots": {"Hi-Jump Boots", "Speed Booster", "Space Jump", "Wall Jump Boots", "Spark Booster", "Blue Booster"},
    "Ammo": {"Missile", "Super Missile", "Power Bomb"},
    "Tanks": {"Energy Tank", "Reserve Tank"},
    "Morph Ball Upgrades": {"Morph Ball", "Bombs", "Spring Ball"},
}
