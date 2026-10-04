"""Generation tests: Map Rando generation with various settings, then the standard Archipelago world tests."""
from . import SMMapRandoTestBase


class TestDefault(SMMapRandoTestBase):
    options = {}

    def test_randomized(self):
        world = self.multiworld.worlds[1]
        self.assertEqual(len(world.rando_output["randomization"]["item_placement"]), 100)
        self.assertTrue(world.rando_output["seed_hash"])


class TestVanillaMapEasy(SMMapRandoTestBase):
    options = {"map_layout": "vanilla", "skill_assumptions_preset": "medium", "quality_of_life_preset": "max",
               "objectives_preset": "none", "doors_preset": "blue"}


class TestHardReducedPool(SMMapRandoTestBase):
    options = {"skill_assumptions_preset": "hard", "item_progression_preset": "desolate",
               "start_location": "randomized", "wall_jump": "collectible", "speed_booster": "split",
               "doors_preset": "beam"}


class TestSmallMap(SMMapRandoTestBase):
    options = {"map_layout": "small", "item_progression_preset": "desolate"}


class TestWildMap(SMMapRandoTestBase):
    options = {"map_layout": "wild", "skill_assumptions_preset": "expert", "area_assignment": "randomized"}


class TestRacePreset(SMMapRandoTestBase):
    options = {"settings_preset": "community_race_season_5", "objectives_preset": "randomized"}


class TestEscapeStart(SMMapRandoTestBase):
    options = {"start_location": "escape"}


class TestCustomStart(SMMapRandoTestBase):
    options = {"start_location": "custom", "custom_start_location": "Bomb Torizo Room", "save_animals": "yes",
               "rando_starting_items": {"Morph": 1, "Missile": 2}}


class TestStartInventoryFromPool(SMMapRandoTestBase):
    options = {"start_inventory_from_pool": {"Morph Ball": 1, "Missile": 3}}


class TestTwoPlayersCommonMap(SMMapRandoTestBase):
    options = {"common_map": "on", "unique_start_locations": True, "start_location": "randomized",
               "common_door_colors": True}

    def world_setup(self, *args, **kwargs):
        from argparse import Namespace
        from BaseClasses import MultiWorld, CollectionState
        from Generate import get_seed_name
        from worlds import AutoWorld
        from worlds.AutoWorld import call_all
        from test.general import gen_steps
        self.multiworld = MultiWorld(2)
        self.multiworld.game = {1: self.game, 2: self.game}
        self.multiworld.player_name = {1: "Tester1", 2: "Tester2"}
        self.multiworld.set_seed(None)
        args = Namespace()
        for name, option in AutoWorld.AutoWorldRegister.world_types[self.game].options_dataclass.type_hints.items():
            value = self.options.get(name, option.default)
            setattr(args, name, {1: option.from_any(value), 2: option.from_any(value)})
        self.multiworld.set_options(args)
        self.multiworld.state = CollectionState(self.multiworld)
        self.world = self.multiworld.worlds[1]
        for step in gen_steps:
            call_all(self.multiworld, step)

    def test_fill(self):
        # (the base test only follows items placed in player 1's own locations, so it is single-player only)
        from Fill import distribute_items_restrictive
        from worlds.AutoWorld import call_all
        distribute_items_restrictive(self.multiworld)
        call_all(self.multiworld, "post_fill")
        self.assertTrue(self.multiworld.fulfills_accessibility())
        self.assertTrue(self.multiworld.can_beat_game())

    def test_shared_map(self):
        w1, w2 = self.multiworld.worlds[1], self.multiworld.worlds[2]
        self.assertEqual(w1.rando_output["randomization"]["map"], w2.rando_output["randomization"]["map"])
        self.assertEqual(w1.rando_output["randomization"]["locked_doors"],
                         w2.rando_output["randomization"]["locked_doors"])
        self.assertNotEqual(w1.rando_output["start_location_name"], w2.rando_output["start_location_name"])
