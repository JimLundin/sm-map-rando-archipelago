"""
How items from other worlds are shown in a Map Rando world: as the closest Map Rando item (sprite, map marker and
message box name), or as a generic Archipelago item.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Mapping, Optional

from BaseClasses import Item

from .Items import name_to_rando_name

if TYPE_CHECKING:
    from . import SMMapRandoWorld

# Items from other Metroid games that correspond to a Map Rando item (Map Rando item names).
# None means: show as a generic Archipelago item.
METROID_ITEM_MATCHING: Mapping[str, Mapping[str, str]] = {
    "Super Metroid": {
        "Energy Tank": "ETank",
        "Missile": "Missile",
        "SuperMissile": "Super",
        "Power Bomb": "PowerBomb",
        "Grappling Beam": "Grapple",
        "X-Ray Scope": "XRayScope",
        "Reserve Tank": "ReserveTank",
        "Charge Beam": "Charge",
        "Ice Beam": "Ice",
        "Wave Beam": "Wave",
        "Spazer": "Spazer",
        "Plasma Beam": "Plasma",
        "Varia Suit": "Varia",
        "Gravity Suit": "Gravity",
        "Morph Ball": "Morph",
        "Bomb": "Bombs",
        "Spring Ball": "SpringBall",
        "Screw Attack": "ScrewAttack",
        "Hi-Jump Boots": "HiJump",
        "Space Jump": "SpaceJump",
        "Speed Booster": "SpeedBooster"
    },
    "SMZ3": {
        "ETank": "ETank",
        "Missile": "Missile",
        "Super": "Super",
        "PowerBomb": "PowerBomb",
        "Grapple": "Grapple",
        "XRay": "XRayScope",
        "ReserveTank": "ReserveTank",
        "Charge": "Charge",
        "Ice": "Ice",
        "Wave": "Wave",
        "Spazer": "Spazer",
        "Plasma": "Plasma",
        "Varia": "Varia",
        "Gravity": "Gravity",
        "Morph": "Morph",
        "Bombs": "Bombs",
        "SpringBall": "SpringBall",
        "ScrewAttack": "ScrewAttack",
        "HiJump": "HiJump",
        "SpaceJump": "SpaceJump",
        "SpeedBooster": "SpeedBooster"
    },
    "Metroid Fusion": {
        "Missile Data": None,
        "Missile Tank": "Missile",
        "Super Missile": None,
        "Ice Missile": None,
        "Diffusion Missile": None,
        "Power Bomb Data": None,
        "Power Bomb Tank": "PowerBomb",
        "Energy Tank": "ETank",
        "Charge Beam": "Charge",
        "Wide Beam": "Spazer",
        "Plasma Beam": "Plasma",
        "Wave Beam": "Wave",
        "Ice Beam": "Ice",
        "Morph Ball": "Morph",
        "Bomb Data": "Bombs",
        "Hi-Jump": "HiJump",
        "Space Jump": "SpaceJump",
        "Speed Booster": "SpeedBooster",
        "Screw Attack": "ScrewAttack",
        "Varia Suit": "Varia",
        "Gravity Suit": "Gravity",
        "Nothing": "Nothing"
    },
    "Metroid Zero Mission": {
        "Energy Tank": "ETank",
        "Missile Tank": "Missile",
        "Super Missile Tank": "Super",
        "Power Bomb Tank": "PowerBomb",
        "Long Beam": None,
        "Charge Beam": "Charge",
        "Ice Beam": "Ice",
        "Wave Beam": "Wave",
        "Plasma Beam": "Plasma",
        "Bomb": "Bombs",
        "Varia Suit": "Varia",
        "Gravity Suit": "Gravity",
        "Morph Ball": "Morph",
        "Speed Booster": "SpeedBooster",
        "Hi-Jump": "HiJump",
        "Screw Attack": "ScrewAttack",
        "Space Jump": "SpaceJump",
        "Power Grip": None,
        "Fully Powered Suit": None,
        "Wall Jump": "WallJump",
        "Spring Ball": "SpringBall"
    },
    "Metroid: Samus Returns": {
        "Missile Launcher": None,
        "Super Missile": None,
        "Power Bomb": None,
        "Wave Beam": "Wave",
        "Spazer Beam": "Spazer",
        "Plasma Beam": "Plasma",
        "Charge Beam": "Charge",
        "Ice Beam": "Ice",
        "Morph Ball": "Morph",
        "Spider Ball": None,
        "Bomb": "Bombs",
        "Spring Ball": "SpringBall",
        "Varia Suit": "Varia",
        "Gravity Suit": "Gravity",
        "Grapple Beam": "Grapple",
        "High Jump Boots": "HiJump",
        "Space Jump": "SpaceJump",
        "Screw Attack": "ScrewAttack",
        "Scan Pulse": None,
        "Lightning Armor": None,
        "Beam Burst": None,
        "Phase Drift": None,
        "Energy Tank": "ETank",
        "Aeion Tank": None,
        "Missile Tank": "Missile",
        "Super Missile Tank": "Super",
        "Power Bomb Tank": "PowerBomb",
        "Energy Reserve Tank": "ReserveTank",
        "Aeion Reserve Tank": None,
        "Missile Reserve Tank": "Missile",
    },
    "Metroid Prime": {
        "Charge Beam": "Charge",
        "Power Beam": None,
        "Progressive Power Beam": None,
        "Super Missile": None,
        "Ice Beam": "Ice",
        "Progressive Ice Beam": "Ice",
        "Ice Spreader": None,
        "Wave Beam": "Wave",
        "Progressive Wave Beam": "Wave",
        "Wavebuster": None,
        "Plasma Beam": "Plasma",
        "Progressive Plasma Beam": "Plasma",
        "Flamethrower": None,
        "Missile Launcher": None,
        "Missile Expansion": "Missile",
        "Power Bomb (Main)": None,
        "Power Bomb Expansion": "PowerBomb",
        "Energy Tank": "ETank",
        "Morph Ball": "Morph",
        "Morph Ball Bomb": "Bombs",
        "Boost Ball": None,
        "Spider Ball": None,
        "Varia Suit": "Varia",
        "Gravity Suit": "Gravity",
        "Phazon Suit": None,
        "Space Jump Boots": "SpaceJump",
        "Grapple Beam": "Grapple",
        "Scan Visor": None,
        "Thermal Visor": None,
        "X-Ray Visor": "XRayScope"
    },
    "Metroid Prime 2 Echoes": {
        "Power Beam": None,
        "Dark Beam": None,
        "Light Beam": None,
        "Annihilator Beam": None,
        "Super Missile": None,
        "Darkburst": None,
        "Sunburst": None,
        "Sonic Boom": None,
        "Combat Visor": None,
        "Scan Visor": None,
        "Dark Visor": None,
        "Echo Visor": None,
        "Dark Suit": None,
        "Light Suit": None,
        "Morph Ball": "Morph",
        "Boost Ball": None,
        "Spider Ball": None,
        "Morph Ball Bomb": "Bombs",
        "Charge Beam": "Charge",
        "Grapple Beam": "Grapple",
        "Space Jump Boots": "SpaceJump",
        "Gravity Boost": None,
        "Seeker Launcher": None,
        "Screw Attack": "ScrewAttack",
        "Energy Tank": "ETank",
        "Power Bomb Expansion": "PowerBomb",
        "Missile Expansion": "Missile",
        "Dark Ammo Expansion": None,
        "Light Ammo Expansion": None,
        "Beam Ammo Expansion": None,
        "Missile Launcher": None,
        "Power Bomb Launcher": None,
        "Unlimited Missiles": None,
        "Unlimited Beam Ammo": None,
        "Energy Transfer Module": None
    }
}


def match_item(world: "SMMapRandoWorld", item: Item) -> Optional[str]:
    """
    Return the Map Rando item (by Map Rando name) used to display an item placed in this world, or None to display it
    as a generic Archipelago item.
    """
    if item.game == world.game:
        rando_name = name_to_rando_name.get(item.name)
    elif world.options.item_matching.value == world.options.item_matching.option_metroid:
        rando_name = METROID_ITEM_MATCHING.get(item.game, {}).get(item.name)
    else:
        rando_name = None
    if rando_name == "Nothing" and item.player != world.player:
        # Map Rando marks locations holding its own Nothing items as already collected, which would make
        # another world's item there unobtainable: show it as a generic item instead.
        return None
    return rando_name
