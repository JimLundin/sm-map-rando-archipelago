"""Stage S1: the player's option values → Map Rando settings (before the engine's `upgrade`).

Milestone 3 has two options: a full-settings preset and the map layout. Milestone 6 generates options for every
setting from Map Rando's schema and presets.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, Mapping

MAP_LAYOUTS = ("Vanilla", "Standard", "Small", "Wild")


def build_settings(preset: Mapping[str, Any], map_layout: str, seed: int) -> Dict[str, Any]:
    if map_layout not in MAP_LAYOUTS:
        raise ValueError(f"unknown map layout {map_layout!r}")
    settings = copy.deepcopy(dict(preset))
    # Map Rando's upgrade re-applies a named full preset over everything else: once we change a setting, the
    # settings are no longer the preset.
    settings["name"] = None
    settings["map_layout"] = map_layout
    settings["other_settings"]["random_seed"] = seed
    settings["other_settings"]["race_mode"] = False
    return settings
