"""Super Metroid Map Rando for Archipelago: the AP adapter. Each hook hands off to a core stage (see
docs/architecture.md); nothing here decides anything about Map Rando.
"""
from __future__ import annotations

import base64
import json
import os
import threading
from collections import Counter
from typing import Any, ClassVar, assert_never

import settings
from BaseClasses import CollectionState, Item, ItemClassification, Location, Region
from Options import OptionError
from worlds.AutoWorld import World

from . import runtime
from .client import SMMRClient  # noqa: F401 (registers the SNI client)
from .core.engine import EngineError, GeneratedWorld
from .core.logic import Classification, Oracle, item_pool
from .core import mwpatch
from .core.mwplan import OtherWorldItem, OwnItem, PlacedItem, plan
from .core.options import build_settings
from .options import SMMROptions, values
from .patch import GAME, SM_JU_MD5, SMMRProcedurePatch

_catalog = runtime.catalog()
_rando_names = {item.name: item.rando_name for item in _catalog.items}
EARLY_LOCATIONS = 4


def ap_classification(classification: Classification) -> ItemClassification:
    match classification:
        case Classification.PROGRESSION:
            return ItemClassification.progression
        case Classification.PROGRESSION_SKIP_BALANCING:
            return ItemClassification.progression_skip_balancing
        case Classification.USEFUL:
            return ItemClassification.useful
        case Classification.FILLER:
            return ItemClassification.filler
        case _:
            assert_never(classification)


def classification(item: Item) -> Classification:
    """Another world's item's classification (traps count as filler)."""
    if item.advancement:
        return Classification.PROGRESSION
    return Classification.USEFUL if item.useful else Classification.FILLER


class SMMRSettings(settings.Group):
    class RomFile(settings.SNESRomPath):
        """File name of the Super Metroid (JU) ROM"""
        description = "Super Metroid (JU) ROM File"
        copy_to = "Super Metroid (JU).sfc"
        md5s = [SM_JU_MD5]

    rom_file: RomFile = RomFile(RomFile.copy_to)


class SMMRItem(Item):
    game = GAME


class SMMRLocation(Location):
    game = GAME


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

    rando_settings: dict[str, Any]
    world: GeneratedWorld
    oracle: Oracle

    def __init__(self, multiworld, player: int):
        super().__init__(multiworld, player)
        self.rom_name = ""
        self.rom_name_ready = threading.Event()

    def generate_early(self) -> None:
        option_values = values(self.options)
        runtime.ensure_map_pool(option_values.map_layout)
        settings_ = build_settings(runtime.full_presets(), option_values, self.random.getrandbits(32))
        engine = runtime.engine()
        try:
            self.rando_settings = engine.upgrade(settings_)
            self.world = engine.world(self.rando_settings, self.random.getrandbits(32))
            session = engine.open(self.rando_settings, self.world.world)
        except EngineError as e:
            raise OptionError(f"{GAME} ({self.player_name}, preset {option_values.preset}): {e}") from e
        self.oracle = Oracle(lambda inventories: engine.reach(session, inventories))

    def _counts(self, state: CollectionState) -> dict[str, int]:
        """Our collected items, by Map Rando name, as the oracle takes them."""
        items = state.prog_items[self.player]
        return {kind.rando_name: items[kind.name] for kind in _catalog.items if items[kind.name]}

    def create_regions(self) -> None:
        # Map Rando's logic decides what's reachable (core.logic); regions only group the locations by area.
        menu = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu)
        regions: dict[str, Region] = {}
        for index in self.world.locations:
            info = _catalog.locations[index]
            if info.area not in regions:
                regions[info.area] = Region(info.area, self.player, self.multiworld)
                self.multiworld.regions.append(regions[info.area])
                menu.connect(regions[info.area])
            location = SMMRLocation(self.player, info.name, info.ap_id, regions[info.area])
            if not self.world.escape:   # (with an escape start, everything is reachable)
                location.access_rule = lambda state, i=index: i in self.oracle.reach(self._counts(state)).locations
            regions[info.area].locations.append(location)
        victory = SMMRLocation(self.player, "Mother Brain", None, menu)
        if not self.world.escape:
            victory.access_rule = lambda state: self.oracle.reach(self._counts(state)).beatable
        victory.place_locked_item(SMMRItem("Victory", ItemClassification.progression, None, self.player))
        menu.locations.append(victory)
        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

    def create_items(self) -> None:
        for item in item_pool(self.world.pool, _catalog):
            self.multiworld.itempool.append(SMMRItem(item.name, ap_classification(item.classification),
                                                     self.item_name_to_id[item.name], self.player))

    def pre_fill(self) -> None:
        """While fewer than EARLY_LOCATIONS of our locations are reachable, place there the item of ours that opens the
        most: with one reachable location at the start (it happens), Archipelago's fill can corner itself."""
        if self.world.escape:
            return
        ours = [item for item in self.multiworld.itempool if item.player == self.player and item.advancement]
        collected: Counter[str] = Counter()
        while True:
            reach = self.oracle.reach(collected)
            open_ = [index for index in sorted(reach.locations)
                     if self.multiworld.get_location(_catalog.locations[index].name, self.player).item is None]
            if len(open_) >= EARLY_LOCATIONS or not open_:
                return
            kinds = sorted({item.name for item in ours})
            opened = {name: len(self.oracle.reach(collected + Counter({_rando_names[name]: 1})).locations)
                      for name in kinds}
            best = max(opened.values(), default=0)
            if best <= len(reach.locations):
                return   # no single item opens more: the fill has to manage
            name = self.random.choice([name for name in kinds if opened[name] == best])
            item = next(item for item in ours if item.name == name)
            ours.remove(item)
            self.multiworld.itempool.remove(item)
            location = self.multiworld.get_location(_catalog.locations[self.random.choice(open_)].name, self.player)
            location.place_locked_item(item)
            collected[_rando_names[name]] += 1

    def create_item(self, name: str) -> Item:
        kind = next(item for item in _catalog.items if item.name == name)
        [item] = item_pool({kind.rando_name: 1}, _catalog)
        return SMMRItem(name, ap_classification(item.classification), self.item_name_to_id[name], self.player)

    def get_filler_item_name(self) -> str:
        return "Missile"

    def generate_output(self, output_directory: str) -> None:
        try:
            self.write_patch(output_directory)
        finally:
            self.rom_name_ready.set()   # modify_multidata waits for it, also when the output failed

    def placement(self) -> list[PlacedItem]:
        """What the fill placed at each of our item locations, in location index order."""
        in_map = set(self.world.locations)
        placed: list[PlacedItem] = []
        for info in _catalog.locations:
            if info.index not in in_map:   # not in this map's rooms
                placed.append(OwnItem("Nothing"))
                continue
            item = self.multiworld.get_location(info.name, self.player).item
            assert item is not None
            if item.player == self.player and item.game == GAME:
                placed.append(OwnItem(item.name))
            else:
                placed.append(OtherWorldItem(item.name, self.multiworld.get_player_name(item.player),
                                             classification(item)))
        return placed

    def write_patch(self, output_directory: str) -> None:
        self.rom_name = mwpatch.rom_name(runtime.abi(), self.player, self.multiworld.seed)
        mw = plan(_catalog, self.placement())
        patch = SMMRProcedurePatch(player=self.player, player_name=self.player_name)
        patch.write_file("smmr.json", json.dumps({
            "settings": self.rando_settings, "world": self.world.world, "item_placement": mw.item_placement,
            "foreign_items": mw.foreign_items, "rom_name": self.rom_name}).encode())
        name = self.multiworld.get_out_file_name_base(self.player)
        patch.write(os.path.join(output_directory, f"{name}{patch.patch_file_ending}"))

    def modify_multidata(self, multidata: dict[str, Any]) -> None:
        # The client connects with the ROM name it reads from the ROM.
        self.rom_name_ready.wait()
        if self.rom_name:
            size = runtime.abi().rom["rom_name_size"]
            key = base64.b64encode(runtime.abi().rom_name(self.rom_name)[:size]).decode()
            multidata["connect_names"][key] = multidata["connect_names"][self.player_name]

    def fill_slot_data(self) -> dict[str, Any]:
        return {"seed_hash": self.world.seed_hash,
                "map_layout": self.rando_settings["map_layout"]}

