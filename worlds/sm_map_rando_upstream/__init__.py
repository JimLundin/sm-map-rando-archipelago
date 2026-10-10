from __future__ import annotations

import base64
import copy
import logging
import os
import threading
from collections import Counter
from typing import Any, ClassVar, Dict, List, Optional, TextIO

import settings
from BaseClasses import (CollectionState, Entrance, Item, ItemClassification, Location, LocationProgressType,
                         MultiWorld, Region, Tutorial)
from Options import OptionError
from worlds.AutoWorld import WebWorld, World

from . import native
from .Client import SMMapRandoSNIClient
from .ItemMatching import match_item
from .Items import (ITEM_DATA, ITEMS_START_ID, NOTHING_INDEX, item_name_groups, item_name_to_id,
                    rando_name_to_index, rando_name_to_name)
from .Locations import LOCATIONS, LOCATIONS_START_ID, location_by_room_node, location_name_to_id
from .ap_options import CommonMap
from .Options import SMMROptions
from .settings_builder import build_customize_settings, build_randomizer_settings
from .OptionPresets import OPTION_GROUPS, OPTIONS_PRESETS
from .Rom import ROM_PLAYERDATA_COUNT, SMJUHASH, SMMapRandoProcedurePatch, build_ap_data, credits_text
from .version import WORLD_VERSION

logger = logging.getLogger("Super Metroid Map Rando Upstream")

GAME_NAME = "Super Metroid Map Rando Upstream"


class SMMapRandoSettings(settings.Group):
    class RomFile(settings.SNESRomPath):
        """File name of the Super Metroid (JU) ROM"""
        description = "Super Metroid (JU) ROM File"
        copy_to = "Super Metroid (JU).sfc"
        md5s = [SMJUHASH]

    rom_file: RomFile = RomFile(RomFile.copy_to)


class SMMapRandoWeb(WebWorld):
    theme = "ice"
    tutorials = [Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up Super Metroid Map Rando Upstream for Archipelago multiworld games.",
        "English",
        "multiworld_en.md",
        "multiworld/en",
        ["Archipelago Map Rando contributors"],
    )]
    option_groups = OPTION_GROUPS
    options_presets = OPTIONS_PRESETS


class MapRandoGenerationError(Exception):
    pass


class SMMRLocation(Location):
    game: str = GAME_NAME

    def __init__(self, player: int, name: str, address: Optional[int], parent: Optional[Region], step: int):
        super().__init__(player, name, address, parent)
        self.step = step


class SMMRItem(Item):
    game: str = GAME_NAME

    def __init__(self, name: str, classification: ItemClassification, code: Optional[int], player: int, step: int):
        super().__init__(name, classification, code, player)
        self.step = step


class SMMapRandoWorld(World):
    """
    After planet Zebes exploded, Mother Brain put it back together again, but arranged it differently this time.

    Super Metroid Map Rando randomizes the map layout (how rooms connect), item locations, door colors, objectives and
    more, with logic covering a wide range of techniques, from casual to insane.
    """

    game = GAME_NAME
    options_dataclass = SMMROptions
    options: SMMROptions
    settings: ClassVar[SMMapRandoSettings]
    settings_key = "sm_map_rando_upstream_options"
    web = SMMapRandoWeb()
    topology_present = True

    item_name_to_id = item_name_to_id
    location_name_to_id = location_name_to_id
    item_name_groups = item_name_groups

    # results of the Map Rando randomizer
    rando_settings: Dict[str, Any]
    rando_output: Dict[str, Any]

    def __init__(self, multiworld: MultiWorld, player: int):
        super().__init__(multiworld, player)
        self.rom_name_available_event = threading.Event()
        self.rom_name = b""
        self.location_steps: Dict[str, int] = {}
        self.num_steps = 0

    # ------------------------------------------------------------------------------------------------------------
    # Generation

    @classmethod
    def stage_generate_early(cls, multiworld: MultiWorld) -> None:
        worlds: List[SMMapRandoWorld] = sorted(multiworld.get_game_worlds(GAME_NAME), key=lambda w: w.player)
        for world in worlds:
            world.prepare_settings()

        # Worlds sharing a map layout ("common_map" set to a group name) are generated using the same map seed.
        groups: Dict[str, List[SMMapRandoWorld]] = {}
        for world in worlds:
            group = world.options.common_map.value
            if group not in CommonMap.options.values():
                groups.setdefault(str(group), []).append(world)
            elif group == CommonMap.option_on:
                groups.setdefault("\0all", []).append(world)

        for name, members in groups.items():
            reference = members[0]
            for world in members[1:]:
                for key in ("map_layout",):
                    if world.rando_settings[key] != reference.rando_settings[key]:
                        raise OptionError(f"Super Metroid Map Rando Upstream: players {reference.player_name} and "
                                          f"{world.player_name} share a map layout but have different "
                                          f"'{key}' settings.")
                if (world.rando_settings["other_settings"]["area_assignment"]
                        != reference.rando_settings["other_settings"]["area_assignment"]):
                    raise OptionError(f"Super Metroid Map Rando Upstream: players {reference.player_name} and "
                                      f"{world.player_name} share a map layout but have different area assignment "
                                      f"settings.")
            cls.randomize_group(multiworld, members)
        grouped = {w.player for members in groups.values() for w in members}
        for world in worlds:
            if world.player not in grouped:
                world.run_randomizer(None)

    @classmethod
    def randomize_group(cls, multiworld: MultiWorld, members: List["SMMapRandoWorld"]) -> None:
        """
        Randomize worlds sharing a map layout: the first world is randomized normally, and the others then use its map
        (and door colors, with common_door_colors). If another world can't be generated with that map, the first world
        is randomized again, with another map.
        """
        import json
        leader, followers = members[0], members[1:]
        max_tries = 10
        for attempt in range(max_tries):
            leader.run_randomizer(None)
            shared = {
                "map_json": json.dumps(leader.rando_output["randomization"]["map"]),
                "door_seed": leader.rando_output["door_randomization_seed"],
                "used_starts": [leader.rando_output["start_location_name"]],
            }
            world = leader
            try:
                for world in followers:
                    world.run_randomizer(shared, allow_retry=False)
                return
            except MapRandoGenerationError as e:
                logger.info(f"Super Metroid Map Rando Upstream: shared map attempt {attempt + 1} failed for player "
                            f"{world.player_name} ({e}), trying another map")
        raise Exception(f"Super Metroid Map Rando Upstream failed to generate games with a shared map for players "
                        f"{', '.join(w.player_name for w in members)} after {max_tries} maps.")

    def prepare_settings(self) -> None:
        try:
            settings_json = build_randomizer_settings(self)
            self.rando_settings = native.upgrade_settings(settings_json)
        except OptionError:
            raise
        except Exception as e:
            raise OptionError(f"Super Metroid Map Rando Upstream: invalid settings for player {self.player_name}: "
                              f"{e}") from e

    def run_randomizer(self, shared: Optional[Dict[str, Any]], allow_retry: bool = True) -> None:
        kwargs: Dict[str, Any] = {}
        used_starts: Optional[List[str]] = None
        if shared is not None:
            kwargs["fixed_map_json"] = shared["map_json"]
            kwargs["max_attempts"] = 500  # if a shared map doesn't work out, another one is tried
            if self.options.common_door_colors:
                kwargs["fixed_door_seed"] = shared["door_seed"]
            if self.options.unique_start_locations:
                used_starts = shared["used_starts"]
                kwargs["forbidden_start_locations"] = list(used_starts)
        seed = self.random.randrange(1, 1 << 32)
        try:
            self.rando_output = native.randomize(self.rando_settings, seed, **kwargs)
        except Exception as e:
            if "forbidden_start_locations" in kwargs:
                logger.warning(f"Super Metroid Map Rando Upstream: could not find a unique start location for player "
                               f"{self.player_name}, allowing a shared one ({e})")
                del kwargs["forbidden_start_locations"]
                try:
                    self.rando_output = native.randomize(self.rando_settings, seed, **kwargs)
                except Exception as e2:
                    raise MapRandoGenerationError(str(e2)) from e2
            elif shared is not None and not allow_retry:
                raise MapRandoGenerationError(str(e)) from e
            else:
                raise Exception(f"Super Metroid Map Rando Upstream failed to generate a game for player "
                                f"{self.player_name}: {e}. The settings may be too restrictive (for example, a low "
                                f"skill assumptions preset combined with collectible wall jump or beam doors and the "
                                f"ship start location); try a random start location or a higher skill preset.") from e
        if used_starts is not None:
            used_starts.append(self.rando_output["start_location_name"])

    def generate_early(self) -> None:
        # Randomization happens in stage_generate_early, which runs after generate_early of all worlds (so that worlds
        # sharing a map layout can be coordinated).
        pass

    # ------------------------------------------------------------------------------------------------------------
    # Regions and logic
    #
    # The logic comes from Map Rando's own item placement: its spoiler log lists the "steps" in which it collected
    # items. A step's locations are reachable once all items collected in earlier steps are obtained (this is how
    # Map Rando placed them), so each step becomes a region requiring all items of the previous steps.

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu)
        summary = self.rando_output["summary"]

        steps: List[List[Dict[str, Any]]] = [st["items"] for st in summary if st["items"]]
        self.num_steps = len(steps)
        required: Counter = Counter()
        previous = menu
        for step_num, step_items in enumerate(steps, start=1):
            region = Region(f"Step {step_num}", self.player, self.multiworld)
            self.multiworld.regions.append(region)
            requirement = Counter(required)
            entrance = previous.connect(region, f"To Step {step_num}")
            if requirement:
                entrance.access_rule = lambda state, req=requirement: state.has_all_counts(req, self.player)
            for entry in step_items:
                loc = location_by_room_node[(entry["location"]["room_id"], entry["location"]["node_id"])]
                self.location_steps[loc["name"]] = step_num
                region.locations.append(SMMRLocation(self.player, loc["name"], location_name_to_id[loc["name"]],
                                                     region, step_num))
                if entry["item"] != "Nothing":
                    required[rando_name_to_name[entry["item"]]] += 1
            previous = region

        # Locations that Map Rando didn't use in its item placement (e.g. with "stop item placement early", or the
        # Escape start) can only be relied on once everything else is obtained: they only get filler items.
        final = Region("Remaining", self.player, self.multiworld)
        self.multiworld.regions.append(final)
        final_requirement = Counter(required)
        entrance = previous.connect(final, "To Remaining")
        if final_requirement:
            entrance.access_rule = lambda state, req=final_requirement: state.has_all_counts(req, self.player)
        for loc in LOCATIONS:
            if loc["name"] not in self.location_steps:
                location = SMMRLocation(self.player, loc["name"], location_name_to_id[loc["name"]], final,
                                        self.num_steps + 1)
                if self.num_steps > 0:
                    location.progress_type = LocationProgressType.EXCLUDED
                final.locations.append(location)

        victory = SMMRLocation(self.player, "Mother Brain", None, final, self.num_steps + 1)
        victory.place_locked_item(SMMRItem("Victory", ItemClassification.progression, None, self.player,
                                           self.num_steps + 1))
        final.locations.append(victory)

    def create_items(self) -> None:
        placement: List[str] = self.rando_output["randomization"]["item_placement"]
        in_logic: Counter = Counter()
        for st in self.rando_output["summary"]:
            for entry in st["items"]:
                in_logic[(entry["location"]["room_id"], entry["location"]["node_id"])] += 1

        pool = []
        for loc in LOCATIONS:
            rando_name = placement[loc["index"]]
            name = rando_name_to_name[rando_name]
            data = ITEM_DATA[rando_name_to_index[rando_name]]
            step = self.location_steps.get(loc["name"], self.num_steps + 1)
            if rando_name == "Nothing":
                classification = ItemClassification.filler
            elif (loc["room_id"], loc["node_id"]) in in_logic:
                classification = ItemClassification.progression
            elif self.num_steps == 0 and (data.unique or rando_name in ("ETank", "ReserveTank")):
                # Escape start: no item is needed, but upgrades are still nice to have
                classification = ItemClassification.useful
            else:
                # Items that Map Rando placed outside of its logic (e.g. after "stop item placement early"): their
                # locations only get filler, so the items must be filler too.
                classification = ItemClassification.filler
            pool.append(SMMRItem(name, classification, item_name_to_id[name], self.player, step))
        self.multiworld.itempool += self.lock_bottleneck_steps(pool)

    def set_rules(self) -> None:
        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

    def create_item(self, name: str) -> Item:
        if name in ("Missile", "Super Missile", "Power Bomb", "Nothing"):
            classification = ItemClassification.filler
        elif name in ("Energy Tank", "Reserve Tank"):
            classification = ItemClassification.useful
        else:
            classification = ItemClassification.progression
        return SMMRItem(name, classification, item_name_to_id[name], self.player, 0)

    def get_filler_item_name(self) -> str:
        return self.random.choice(["Missile", "Missile", "Missile", "Super Missile", "Power Bomb"])

    # Steps of Map Rando's item placement with fewer item locations than this are kept local (bottlenecks).
    EARLY_STEP_MAX_LOCATIONS = 5

    def lock_bottleneck_steps(self, pool: List["SMMRItem"]) -> List["SMMRItem"]:
        """Place the items of steps with very few locations at their Map Rando locations. Returns the other items."""
        if not self.options.local_early_progression:
            return pool
        steps: Dict[int, List[SMMRLocation]] = {}
        for location in self.multiworld.get_locations(self.player):
            if isinstance(location, SMMRLocation) and location.address is not None and location.step <= self.num_steps:
                steps.setdefault(location.step, []).append(location)
        items: Dict[int, List[SMMRItem]] = {}
        for item in pool:
            if item.advancement:
                items.setdefault(item.step, []).append(item)
        placed = set()
        for step in range(1, self.num_steps + 1):
            step_locations = steps.get(step, [])
            step_items = items.get(step, [])
            if len(step_locations) >= self.EARLY_STEP_MAX_LOCATIONS or len(step_items) != len(step_locations):
                continue
            self.random.shuffle(step_items)
            for location, item in zip(sorted(step_locations, key=lambda x: x.name), step_items):
                location.place_locked_item(item)
                placed.add(id(item))
        return [item for item in pool if id(item) not in placed]

    def fill_hook(self, progitempool: List[Item], usefulitempool: List[Item], filleritempool: List[Item],
                  fill_locations: List[Location]) -> None:
        # Help the fill by ordering our items and locations by Map Rando step: this way the items needed earliest
        # are placed first, into the earliest steps' locations.
        def sort_by_step(items: List[Any], reverse: bool = False) -> None:
            indexes = [i for i, x in enumerate(items) if x.player == self.player and hasattr(x, "step")]
            ours = sorted((items[i] for i in indexes), key=lambda x: x.step, reverse=reverse)
            for i, x in zip(indexes, ours):
                items[i] = x

        sort_by_step(progitempool, True)
        sort_by_step(fill_locations)

    # ------------------------------------------------------------------------------------------------------------
    # Output

    def get_item_placement_and_ap_data(self) -> tuple:
        """The item placement as seen by the Map Rando patcher, and the Archipelago item table data."""
        placement: List[str] = list(self.rando_output["randomization"]["item_placement"])
        location_items = []
        player_ids = {0, self.player}
        own_locations = {loc.name: loc for loc in self.multiworld.get_locations(self.player) if loc.address}
        for info in LOCATIONS:
            location = own_locations[info["name"]]
            item = location.item
            assert item is not None
            if item.player == self.player:
                dest_type = 0
            elif item.player in self.multiworld.groups and \
                    self.player in self.multiworld.groups[item.player]["players"]:
                dest_type = 2  # item link that includes us
            else:
                dest_type = 1
            matched = match_item(self, item)
            if matched is None:
                item_id = None
                # Map markers: off-world items are shown like the closest kind of Map Rando item.
                if item.advancement:
                    placement[info["index"]] = "Bombs"
                elif item.useful:
                    placement[info["index"]] = "ETank"
                else:
                    placement[info["index"]] = "Missile"
            else:
                item_id = rando_name_to_index[matched]
                placement[info["index"]] = matched
            player_ids.add(item.player)
            location_items.append((info["bit_index"], dest_type, item_id, bool(item.advancement), item.name,
                                   item.player))

        # Also include players who have items for us (so received messages can show their names)
        for location in self.multiworld.get_locations():
            if location.item and location.item.player == self.player:
                player_ids.add(location.player)
        ids = sorted(player_ids)
        if len(ids) > ROM_PLAYERDATA_COUNT:
            logger.warning(f"Super Metroid Map Rando Upstream: player {self.player_name} interacts with too many "
                           f"players to fit in ROM; some received-from names will show as Archipelago.")
            keep = {0, self.player} | {x[5] for x in location_items}
            ids = sorted(keep | set(i for i in ids if i not in keep)[:max(0, ROM_PLAYERDATA_COUNT - len(keep))]) \
                if len(keep) <= ROM_PLAYERDATA_COUNT else sorted(keep)[:ROM_PLAYERDATA_COUNT]
        return placement, location_items, ids

    def credits_spoiler_info(self) -> List[Dict[str, Any]]:
        """Item credits: in which sphere and where each of our major items was found."""
        infos = copy.deepcopy(self.rando_output["randomization"]["essential_spoiler_data"]["item_spoiler_info"])
        found: Dict[str, tuple] = {}
        for sphere_idx, sphere in enumerate(self.multiworld.get_spheres(), start=1):
            for location in sphere:
                item = location.item
                if item is None or item.player != self.player or item.code is None:
                    continue
                rando_name = ITEM_DATA[item.code - ITEMS_START_ID].rando_name
                if rando_name in found:
                    continue
                if location.player == self.player:
                    area = None
                else:
                    area = credits_text(self.multiworld.get_player_name(location.player))
                found[rando_name] = (sphere_idx, area)
        for info in infos:
            if info["item"] in found:
                sphere_idx, area = found[info["item"]]
                info["step"] = sphere_idx
                if area is not None:
                    info["area"] = area
        return infos

    def generate_output(self, output_directory: str) -> None:
        try:
            placement, location_items, player_ids = self.get_item_placement_and_ap_data()
            randomization = copy.deepcopy(self.rando_output["randomization"])
            randomization["item_placement"] = placement
            randomization["essential_spoiler_data"]["item_spoiler_info"] = self.credits_spoiler_info()

            from Utils import __version__
            self.rom_name = (f"SMMU{__version__.replace('.', '')[:3]}_{self.player}_"
                             f"{self.multiworld.seed:011}").encode("ascii")[:21]
            data = {
                "settings": self.rando_settings,
                "randomization": randomization,
                "customize": build_customize_settings(self),
                "ap": build_ap_data(self, location_items, player_ids),
                "rom_name": self.rom_name.decode("ascii"),
                "world_version": WORLD_VERSION,
            }
            import json
            patch = SMMapRandoProcedurePatch(player=self.player, player_name=self.player_name)
            patch.write_file("rando_data.json", json.dumps(data).encode("utf-8"))
            out_file_base = self.multiworld.get_out_file_name_base(self.player)
            patch.write(os.path.join(output_directory, f"{out_file_base}{patch.patch_file_ending}"))
        finally:
            self.rom_name_available_event.set()  # make sure threading continues and errors are collected

    def modify_multidata(self, multidata: Dict[str, Any]) -> None:
        # wait for self.rom_name to be available.
        self.rom_name_available_event.wait()
        if self.rom_name:
            new_name = base64.b64encode(self.rom_name.ljust(21, b"\0")).decode()
            multidata["connect_names"][new_name] = multidata["connect_names"][self.player_name]

    def fill_slot_data(self) -> Dict[str, Any]:
        out = self.rando_output
        return {
            "seed_hash": out["seed_hash"],
            "start_location": out["start_location_name"],
            "objectives": out["objectives"],
            "map_layout": self.rando_settings["map_layout"],
            "death_link": self.options.death_link.value,
            "remote_items": self.options.remote_items.value,
        }

    def extend_hint_information(self, hint_data: Dict[int, Dict[int, str]]) -> None:
        if self.rando_settings["map_layout"] == "Vanilla":
            return
        player_hint_data = {}
        for st in self.rando_output["summary"]:
            for entry in st["items"]:
                loc = location_by_room_node[(entry["location"]["room_id"], entry["location"]["node_id"])]
                player_hint_data[location_name_to_id[loc["name"]]] = entry["location"]["area"]
        hint_data[self.player] = player_hint_data

    def write_spoiler_header(self, spoiler_handle: TextIO) -> None:
        out = self.rando_output
        spoiler_handle.write(f"Map Rando seed hash:             {out['seed_hash']}\n")
        spoiler_handle.write(f"Map Rando map layout:            {self.rando_settings['map_layout']}\n")
        spoiler_handle.write(f"Map Rando start location:        {out['start_location_name']}\n")
        spoiler_handle.write(f"Map Rando objectives:            {', '.join(out['objectives'])}\n")

    def interpret_slot_data(self, slot_data: Dict[str, Any]) -> None:
        pass
