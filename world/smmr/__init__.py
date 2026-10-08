"""Super Metroid Map Rando for Archipelago: the AP adapter. Each hook hands off to a core stage (see
docs/architecture.md); nothing here decides anything about Map Rando.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List

import settings
from BaseClasses import Item, ItemClassification, Location, LocationProgressType, Region
from Options import Choice, OptionError, PerGameCommonOptions
from worlds.AutoWorld import World

from . import runtime
from .core.engine import EngineError
from .core.logic import FILLER, PROGRESSION, USEFUL, LogicModel, build_logic
from .core.mwplan import PlacedItem, plan
from .core.options import build_settings
from .patch import GAME, SM_JU_MD5, SMMRProcedurePatch

CLASSIFICATIONS = {PROGRESSION: ItemClassification.progression, USEFUL: ItemClassification.useful,
                   FILLER: ItemClassification.filler}
_catalog = runtime.catalog()


class SMMRSettings(settings.Group):
    class RomFile(settings.SNESRomPath):
        """File name of the Super Metroid (JU) ROM"""
        description = "Super Metroid (JU) ROM File"
        copy_to = "Super Metroid (JU).sfc"
        md5s = [SM_JU_MD5]

    rom_file: RomFile = RomFile(RomFile.copy_to)


class Preset(Choice):
    """Map Rando's full-settings preset (as on maprando.com)."""
    display_name = "Preset"
    option_default = 0
    option_community_race_season_5 = 1
    option_mentor_tournament = 2
    option_summer_series_expert_challenge = 3
    default = 0
    preset_names = {0: "Default", 1: "Community Race Season 5", 2: "Mentor Tournament",
                    3: "Summer Series Expert Challenge"}


class MapLayout(Choice):
    """How rooms are connected. Vanilla is the original map; the others are Map Rando's map pools."""
    display_name = "Map Layout"
    option_vanilla = 0
    option_standard = 1
    option_small = 2
    option_wild = 3
    default = 1


@dataclass
class SMMROptions(PerGameCommonOptions):
    preset: Preset
    map_layout: MapLayout


class SMMRItem(Item):
    game = GAME
    step = 0   # the Map Rando step whose locations Map Rando put the item in (see core.logic)


class SMMRLocation(Location):
    game = GAME
    step = 0


class SMMRWorld(World):
    """Super Metroid with a randomized map layout, item placement, doors and objectives, by Map Rando."""

    game = GAME
    options_dataclass = SMMROptions
    options: SMMROptions
    settings: ClassVar[SMMRSettings]
    settings_key = "smmr_options"
    topology_present = True

    item_name_to_id = {item.name: item.ap_id for item in _catalog.items}
    location_name_to_id = {loc.name: loc.ap_id for loc in _catalog.locations}

    rando_settings: Dict[str, Any]
    seed_artifact: Dict[str, Any]
    logic: LogicModel

    def generate_early(self) -> None:
        preset_name = self.options.preset.preset_names[self.options.preset.value]
        settings_ = build_settings(runtime.preset(preset_name), self.options.map_layout.current_option_name,
                                   self.random.getrandbits(32))
        try:
            self.rando_settings = runtime.engine().upgrade(settings_)
            self.seed_artifact = runtime.engine().randomize(self.rando_settings, self.random.getrandbits(32))
        except EngineError as e:
            raise OptionError(f"{GAME} ({self.player_name}, preset {preset_name}): {e}") from e
        self.logic = build_logic(self.seed_artifact, _catalog)

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu)
        previous = menu
        for step in (*self.logic.steps, self.logic.remaining):
            region = Region(f"Step {step.number}", self.player, self.multiworld)
            self.multiworld.regions.append(region)
            entrance = previous.connect(region, f"To Step {step.number}")
            if step.requires:
                entrance.access_rule = lambda state, req=dict(step.requires): state.has_all_counts(req, self.player)
            for index in step.locations:
                info = _catalog.locations[index]
                location = SMMRLocation(self.player, info.name, info.ap_id, region)
                location.step = step.number
                if step is self.logic.remaining and self.logic.steps:
                    location.progress_type = LocationProgressType.EXCLUDED
                region.locations.append(location)
            previous = region
        victory = SMMRLocation(self.player, "Mother Brain", None, previous)
        victory.place_locked_item(SMMRItem("Victory", ItemClassification.progression, None, self.player))
        previous.locations.append(victory)
        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

    def create_items(self) -> None:
        for item in self.logic.pool:
            ap_item = SMMRItem(item.name, CLASSIFICATIONS[item.classification], self.item_name_to_id[item.name],
                               self.player)
            ap_item.step = item.step
            self.multiworld.itempool.append(ap_item)

    def fill_hook(self, progitempool: List[Item], usefulitempool: List[Item], filleritempool: List[Item],
                  fill_locations: List[Location]) -> None:
        # Every step requires all items of the earlier steps, so a random fill rarely fits. Map Rando's own order
        # does: our items are placed earliest step first (the fill pops from the end), and the earliest steps'
        # locations come first. Other worlds' items and locations keep their positions.
        def reorder(entries: List[Any], reverse: bool) -> None:
            ours = [i for i, x in enumerate(entries) if isinstance(x, (SMMRItem, SMMRLocation)) and x.player == self.player]
            for i, x in zip(ours, sorted((entries[i] for i in ours), key=lambda x: x.step, reverse=reverse)):
                entries[i] = x

        reorder(progitempool, reverse=True)
        reorder(fill_locations, reverse=False)

    def create_item(self, name: str) -> Item:
        unique = next(item.unique for item in _catalog.items if item.name == name)
        classification = ItemClassification.progression if unique else ItemClassification.filler
        return SMMRItem(name, classification, self.item_name_to_id[name], self.player)

    def get_filler_item_name(self) -> str:
        return "Missile"

    def generate_output(self, output_directory: str) -> None:
        placed = []
        for info in _catalog.locations:
            item = self.multiworld.get_location(info.name, self.player).item
            assert item is not None
            placed.append(PlacedItem(item.name, item.player, item.game))
        mw = plan(_catalog, placed, self.player, self.game)
        randomization = dict(self.seed_artifact["randomization"], item_placement=mw.item_placement)
        patch = SMMRProcedurePatch(player=self.player, player_name=self.player_name)
        patch.write_file("smmr.json", json.dumps({"settings": self.rando_settings,
                                                  "randomization": randomization}).encode())
        name = self.multiworld.get_out_file_name_base(self.player)
        patch.write(os.path.join(output_directory, f"{name}{patch.patch_file_ending}"))

    def fill_slot_data(self) -> Dict[str, Any]:
        return {"seed_hash": self.seed_artifact["seed_hash"],
                "map_layout": self.rando_settings["map_layout"]}

