"""Stage S1: the player's option values → Map Rando settings (before the engine's `upgrade`).

The options mirror the website's top level: a full-settings preset, then each settings category's preset (or the
full preset's own), the map layout, the start location and a few single settings. A category is chosen by its preset
name only: Map Rando's upgrade expands named category presets.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

MAP_LAYOUTS = ("Vanilla", "Standard", "Small", "Wild")
START_LOCATIONS = ("Ship", "Random", "Escape")
WALL_JUMP = ("Vanilla", "Collectible")
SAVE_ANIMALS = ("No", "Optional", "Yes", "Random")

# The option for each settings category: (option name, settings field)
CATEGORIES = {
    "skill_assumptions": "skill_assumption_settings",
    "item_progression": "item_progression_settings",
    "quality_of_life": "quality_of_life_settings",
    "objectives": "objective_settings",
    "doors": "doors_settings",
}


def option_key(name: str) -> str:
    """An Archipelago option value name for a Map Rando name: "Very Hard" → very_hard, "Expert+" → expert_plus,
    "Random" → randomized (Archipelago reserves `random` for picking a value at random)."""
    key = re.sub(r"[^a-z0-9]+", "_", name.lower().replace("+", "_plus")).strip("_")
    return "randomized" if key == "random" else key


@dataclass(frozen=True)
class OptionValues:
    preset: str                                  # full-settings preset name
    map_layout: str = "Standard"
    categories: Mapping[str, Optional[str]] = field(default_factory=dict)   # option name → preset, None: the preset's
    start_location: Optional[str] = None         # None: the preset's
    wall_jump: Optional[str] = None
    save_animals: Optional[str] = None


def build_settings(full_presets: Mapping[str, Mapping[str, Any]], values: OptionValues, seed: int) -> Dict[str, Any]:
    if values.map_layout not in MAP_LAYOUTS:
        raise ValueError(f"unknown map layout {values.map_layout!r}")
    settings = copy.deepcopy(dict(full_presets[values.preset]))
    # Map Rando's upgrade re-applies a named full preset over everything else: once we change a setting, the
    # settings are no longer the preset.
    settings["name"] = None
    settings["map_layout"] = values.map_layout
    for option, preset in values.categories.items():
        if preset is not None:   # the upgrade replaces the category with the named preset
            settings[CATEGORIES[option]] = {**settings[CATEGORIES[option]], "preset": preset}
    if values.start_location is not None:
        # (older presets don't have the field yet: the upgrade fills in the rest)
        settings["start_location_settings"] = {**settings.get("start_location_settings", {}),
                                               "mode": values.start_location}
    other = settings.setdefault("other_settings", {})
    if values.wall_jump is not None:
        other["wall_jump"] = values.wall_jump
    if values.save_animals is not None:
        settings["save_animals"] = values.save_animals
    other["random_seed"] = seed
    other["race_mode"] = False
    return settings
