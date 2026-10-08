"""The AP options, built from Map Rando's presets (data/presets.json, data/info.json) when the world loads: a new
upstream preset is a new option value without code changes. `values()` turns them into S1's `OptionValues`."""
from __future__ import annotations

from dataclasses import make_dataclass
from typing import Dict, List, Optional, Sequence, Type

from Options import Choice, DefaultOnToggle, PerGameCommonOptions

from . import runtime
from .core.options import (CATEGORIES, MAP_LAYOUTS, SAVE_ANIMALS, START_LOCATIONS, WALL_JUMP, OptionValues,
                           option_key)

FROM_PRESET = "Preset"   # value 0 of an override: keep the full preset's


class MapRandoChoice(Choice):
    rando_names: List[Optional[str]]   # Map Rando name of each option value (None: the full preset's)

    @property
    def rando_name(self) -> Optional[str]:
        return self.rando_names[self.value]


def _choice(class_name: str, display_name: str, doc: str, names: Sequence[Optional[str]], default: int = 0) -> Type:
    attrs: Dict[str, object] = {"__doc__": doc, "__module__": __name__, "display_name": display_name,
                                "default": default, "rando_names": list(names)}
    for value, name in enumerate(names):
        attrs[f"option_{option_key(name or FROM_PRESET)}"] = value
    option = type(class_name, (MapRandoChoice,), attrs)
    globals()[class_name] = option
    return option


_full = sorted(runtime.full_presets(), key=lambda name: name != "Default")
_categories = runtime.catalog_info()["category_presets"]
_DOCS = {
    "skill_assumptions": "Which techniques the logic may require (Map Rando's skill assumptions preset).",
    "item_progression": "How items are placed: progression speed, item pool, filler (item progression preset).",
    "quality_of_life": "Map, item markers, faster animations and other conveniences (quality-of-life preset).",
    "objectives": "What must be done before Mother Brain (objectives preset).",
    "doors": "Which doors are locked and with what (doors preset).",
}

OPTION_TYPES: Dict[str, Type] = {
    "preset": _choice("Preset", "Preset", "Map Rando's full-settings preset (maprando.com). The options below "
                      "replace parts of it.", _full),
    "map_layout": _choice("MapLayout", "Map Layout", "How rooms are connected. Vanilla is the original map; the "
                          "others are Map Rando's map pools (downloaded when first used).", MAP_LAYOUTS,
                          default=MAP_LAYOUTS.index("Standard")),
    **{option: _choice("".join(part.title() for part in option.split("_")), option.replace("_", " ").title(),
                       _DOCS[option] + " Preset: the full preset's.", [None, *_categories[field]])
       for option, field in CATEGORIES.items()},
    "start_location": _choice("StartLocation", "Start Location", "Where Samus starts. Escape: the game starts in "
                              "the escape. Preset: the full preset's.", [None, *START_LOCATIONS]),
    "wall_jump": _choice("WallJump", "Wall Jump", "Collectible: wall jumping needs the Wall Jump Boots item. "
                         "Preset: the full preset's.", [None, *WALL_JUMP]),
    "save_animals": _choice("SaveAnimals", "Save the Animals", "Whether the animals must be saved during the "
                            "escape. Preset: the full preset's.", [None, *SAVE_ANIMALS]),
}

class LocalEarlyProgression(DefaultOnToggle):
    """Keep Map Rando's own items in its first, narrowest item placement steps (fewer than 5 locations). Without
    it, a multiworld fill can fail when other worlds' items take those few locations."""
    display_name = "Local Early Progression"


OPTION_TYPES["local_early_progression"] = LocalEarlyProgression

SMMROptions = make_dataclass("SMMROptions", list(OPTION_TYPES.items()), bases=(PerGameCommonOptions,))
SMMROptions.__module__ = __name__


def values(options) -> OptionValues:
    return OptionValues(
        preset=options.preset.rando_name,
        map_layout=options.map_layout.rando_name,
        categories={option: getattr(options, option).rando_name for option in CATEGORIES},
        start_location=options.start_location.rando_name,
        wall_jump=options.wall_jump.rando_name,
        save_animals=options.save_animals.rando_name,
    )

