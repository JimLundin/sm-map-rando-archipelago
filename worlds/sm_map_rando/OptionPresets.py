"""Option groups and presets for the Archipelago website."""
from __future__ import annotations

from typing import Any, Dict, List

from Options import OptionGroup

from .ap_options import (CommonDoorColors, CommonMap, DeathLink, ItemMatching, LocalEarlyProgression,
                         MapRandoSettings, RemoteItems,
                         SettingsPreset, UniqueStartLocations)
from .Options import OPTION_GROUP_CLASSES

OPTION_GROUPS: List[OptionGroup] = [
    OptionGroup("Archipelago", [DeathLink, RemoteItems, ItemMatching, CommonMap, CommonDoorColors,
                                UniqueStartLocations, LocalEarlyProgression]),
    OptionGroup("Map Rando Settings Preset", [SettingsPreset, MapRandoSettings]),
] + [OptionGroup(name, classes, start_collapsed=name not in ("Map Rando Presets",))
     for name, classes in OPTION_GROUP_CLASSES.items()]

# The website's full settings presets.
OPTIONS_PRESETS: Dict[str, Dict[str, Any]] = {
    "Map Rando Default": {"settings_preset": "default"},
    "Community Race Season 5": {"settings_preset": "community_race_season_5"},
    "Mentor Tournament": {"settings_preset": "mentor_tournament"},
    "Summer Series Expert Challenge": {"settings_preset": "summer_series_expert_challenge"},
}
