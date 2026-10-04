"""Option groups and presets for the Archipelago website."""
from __future__ import annotations

from typing import Any, Dict, List

from Options import OptionGroup

from .ap_options import (CommonDoorColors, CommonMap, DeathLink, ItemMatching, LocalEarlyProgression,
                         MapRandoSettings, RemoteItems, UniqueStartLocations)
from .Options import FULL_PRESET_OPTIONS, OPTION_GROUP_CLASSES, SettingsPreset

OPTION_GROUPS: List[OptionGroup] = [
    OptionGroup("Archipelago", [DeathLink, RemoteItems, ItemMatching, CommonMap, CommonDoorColors,
                                UniqueStartLocations, LocalEarlyProgression]),
    OptionGroup("Map Rando Settings Preset", [SettingsPreset, MapRandoSettings]),
] + [OptionGroup(name, classes, start_collapsed=name not in ("Map Rando Presets",))
     for name, classes in OPTION_GROUP_CLASSES.items()]

# The website's full settings presets.
OPTIONS_PRESETS: Dict[str, Dict[str, Any]] = dict(FULL_PRESET_OPTIONS)
