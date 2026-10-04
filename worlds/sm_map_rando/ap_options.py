"""Archipelago-specific options for Super Metroid Map Rando (not Map Rando settings)."""
from __future__ import annotations

from Options import Choice, DefaultOnToggle, OptionDict, Range, TextChoice, Toggle


class MapRandoSettings(OptionDict):
    """
    Complete Map Rando settings, as exported from the maprando.com website (the settings JSON from "Save settings" /
    a seed's settings), for example:

    map_rando_settings:
      version: 123
      name: Custom
      skill_assumption_settings:
        preset: Hard
      ...

    When given, these settings are used as the base instead of settings_preset and the category presets (individual
    setting options that aren't 'preset' still apply on top). Settings from older Map Rando versions are upgraded.
    "random_seed" is ignored: the Archipelago seed is used.
    """
    display_name = "Map Rando settings JSON"
    default = {}


class DeathLink(Choice):
    """When DeathLink is enabled and someone dies, you will die. With survive reserve tanks can save you."""
    display_name = "Death Link"
    option_disable = 0
    option_enable = 1
    option_enable_survive = 3
    alias_false = 0
    alias_true = 1
    default = 0


class RemoteItems(Toggle):
    """Indicates you get items sent from your own world. This allows coop play of a world."""
    display_name = "Remote Items"


class ItemMatching(Choice):
    """
    Changes how items from other worlds appear:
    - Metroid: Items from other Metroid games will get the closest matching sprite and map item markers.
    - Generic: All items from other worlds will have an Archipelago sprite, with an arrow to indicate progression.
    """
    display_name = "Item matching"
    option_metroid = 0
    option_generic = 1
    default = 0


class CommonMap(TextChoice):
    """
    Share a map layout with other Map Rando players in the multiworld:
    - off: this world gets its own map.
    - on: all Map Rando worlds with common_map 'on' share the same map layout.
    - any other text: a group name; all Map Rando worlds with the same group name share the same map layout.
    Worlds sharing a map must use the same map layout and area assignment settings.
    """
    display_name = "Common map"
    option_off = 0
    option_on = 1
    alias_false = 0
    alias_true = 1
    alias_no = 0
    alias_yes = 1
    default = 0


class CommonDoorColors(Toggle):
    """
    If enabled, worlds sharing a map layout (common_map) also get the same door colors (this requires the same doors
    settings). Ignored if common_map is off.
    """
    display_name = "Common door colors"


class UniqueStartLocations(Toggle):
    """
    If enabled, worlds sharing a map layout (common_map) start at different locations (with random start locations),
    when possible. Ignored if common_map is off.
    """
    display_name = "Unique start locations"


class LocalEarlyProgression(DefaultOnToggle):
    """
    Map Rando places items in steps, and some steps (often the first ones, e.g. the first key item next to the start)
    have only a few reachable item locations. If enabled, the items of steps with fewer than 5 locations are placed at
    their locations in this world, as Map Rando placed them; all other items are shuffled into the multiworld. This
    makes multiworld generation much more reliable. If disabled, generation may fail more often.
    """
    display_name = "Local early progression"
