"""Tests of building Map Rando settings from options (presets and overrides), without generating."""
import unittest
from argparse import Namespace

from BaseClasses import MultiWorld
from worlds.AutoWorld import AutoWorldRegister

from .. import settings_builder
from ..settings_builder import canonical, load_preset

GAME = "Super Metroid Map Rando Upstream"


def make_world(**options):
    multiworld = MultiWorld(1)
    multiworld.game = {1: GAME}
    multiworld.player_name = {1: "Tester"}
    multiworld.set_seed(1)
    world_type = AutoWorldRegister.world_types[GAME]
    args = Namespace()
    for name, option in world_type.options_dataclass.type_hints.items():
        value = options.get(name, option.default)
        setattr(args, name, {1: option.from_any(value)})
    multiworld.set_options(args)
    return multiworld.worlds[1]


def build(**options):
    return settings_builder.build_randomizer_settings(make_world(**options))


def without(d, *keys):
    return {k: v for k, v in d.items() if k not in keys}


class TestSettingsPresets(unittest.TestCase):
    def test_default(self):
        s = build()
        self.assertEqual(s["name"], "Default")
        self.assertEqual(canonical(without(s, "version", "debug")),
                         canonical(without(load_preset("full-settings", "Default"), "version", "debug")))
        self.assertEqual(s["skill_assumption_settings"]["preset"], "Basic")
        self.assertEqual(s["item_progression_settings"]["preset"], "Normal")
        self.assertEqual(s["quality_of_life_settings"]["preset"], "Default")

    def test_full_presets(self):
        for option_value, name in [("default", "Default"), ("community_race_season_5", "Community Race Season 5"),
                                   ("mentor_tournament", "Mentor Tournament"),
                                   ("summer_series_expert_challenge", "Summer Series Expert Challenge")]:
            with self.subTest(name):
                s = build(settings_preset=option_value)
                preset = load_preset("full-settings", name)
                self.assertEqual(s["name"], name)
                self.assertEqual(canonical(without(s, "version", "debug")),
                                 canonical(without(preset, "version", "debug")))
                # preset labels are kept for categories matching a preset
                for category in ["skill_assumption_settings", "item_progression_settings", "quality_of_life_settings",
                                 "objective_settings", "doors_settings"]:
                    self.assertEqual(s[category]["preset"], preset[category]["preset"], category)

    def test_category_presets(self):
        cases = [
            ("skill_assumptions_preset", "skill_assumption_settings", "skill-assumptions",
             {"medium": "Medium", "very_hard": "Very Hard", "expert_plus": "Expert+", "insane_plus": "Insane+",
              "beyond": "Beyond"}),
            ("item_progression_preset", "item_progression_settings", "item-progression",
             {"tricky": "Tricky", "desolate": "Desolate"}),
            ("quality_of_life_preset", "quality_of_life_settings", "quality-of-life",
             {"off": "Off", "max": "Max"}),
            ("objectives_preset", "objective_settings", "objectives",
             {"metroids": "Metroids", "randomized": "Random", "none": "None"}),
            ("doors_preset", "doors_settings", "doors", {"blue": "Blue", "beam": "Beam"}),
        ]
        for option, category, preset_dir, values in cases:
            for value, name in values.items():
                with self.subTest(option=option, value=value):
                    s = build(**{option: value})
                    self.assertEqual(s[category]["preset"], name)
                    self.assertEqual(canonical(s[category]), canonical(load_preset(preset_dir, name)))
                    self.assertIsNone(s["name"])

    def test_override_makes_custom(self):
        s = build(skill_assumptions_preset="hard", shinespark_tiles="17.5", gate_glitch_leniency=4)
        skill = s["skill_assumption_settings"]
        self.assertIsNone(skill["preset"])
        self.assertEqual(skill["shinespark_tiles"], 17.5)
        self.assertEqual(skill["gate_glitch_leniency"], 4)
        self.assertEqual(skill["speed_ball_tiles"], load_preset("skill-assumptions", "Hard")["speed_ball_tiles"])

    def test_override_equal_to_preset_keeps_name(self):
        hard = load_preset("skill-assumptions", "Hard")
        s = build(skill_assumptions_preset="hard", gate_glitch_leniency=hard["gate_glitch_leniency"])
        self.assertEqual(s["skill_assumption_settings"]["preset"], "Hard")

    def test_tech_and_notables(self):
        s = build(tech_enabled=["canWallJump", "Medium"], tech_disabled=["canHeatRun"],
                  notables_enabled=["Crab Hole: Gravity Space Jump Climb"])
        tech = {t["name"]: t["enabled"] for t in s["skill_assumption_settings"]["tech_settings"]}
        self.assertFalse(tech["canHeatRun"])
        self.assertTrue(tech["canWallJump"])
        self.assertTrue(tech["canSuitlessMaridia"])  # a Medium tech
        self.assertIsNone(s["skill_assumption_settings"]["preset"])

    def test_sub_presets(self):
        s = build(crash_fixes="warn", initial_map_reveal="global", enhanced_map="no",
                  map_station_activation="partial", area_assignment="depth")
        qol = s["quality_of_life_settings"]
        self.assertEqual(qol["crash_fixes"]["preset"], "Warn")
        self.assertEqual(qol["crash_fixes"]["x_mode"], "Warn")
        self.assertEqual(qol["crash_fixes"]["sprite_overflow"], "Silent")
        self.assertEqual(qol["initial_map_reveal_settings"]["preset"], "Global")
        self.assertTrue(qol["initial_map_reveal_settings"]["all_areas"])
        self.assertEqual(qol["enhanced_map_settings"]["preset"], "No")
        self.assertEqual(qol["enhanced_map_settings"]["walls"], "Vanilla")
        self.assertEqual(qol["map_station_activation_settings"]["preset"], "Partial")
        self.assertIsNone(qol["preset"])
        area = s["other_settings"]["area_assignment"]
        self.assertEqual(area, {"preset": "Depth", "base_order": "Depth", "ship_in_crateria": False,
                                "mother_brain_in_tourian": False})

    def test_sub_preset_override(self):
        s = build(crash_fixes="warn", crash_fix_x_mode="crash")
        fixes = s["quality_of_life_settings"]["crash_fixes"]
        self.assertIsNone(fixes["preset"])
        self.assertEqual(fixes["x_mode"], "Crash")
        self.assertEqual(fixes["spring_ball"], "Warn")

    def test_items(self):
        s = build(item_pool_preset="reduced", item_pool={"Missile": 20, "Varia": 0},
                  rando_starting_items={"Morph": 1}, key_item_priority={"Varia": "Early"},
                  filler_items={"Super": "Semi"}, missile_size=10)
        items = s["item_progression_settings"]
        pool = {e["item"]: e["count"] for e in items["item_pool"]}
        self.assertEqual(pool["Missile"], 20)
        self.assertEqual(pool["Super"], 6)
        self.assertEqual(pool["Varia"], 0)
        self.assertIsNone(items["item_pool_preset"])
        self.assertTrue(items["stop_item_placement_early"])
        self.assertEqual({e["item"]: e["count"] for e in items["starting_items"]}["Morph"], 1)
        self.assertEqual({e["item"]: e["priority"] for e in items["key_item_priority"]}["Varia"], "Early")
        self.assertEqual({e["item"]: e["priority"] for e in items["filler_items"]}["Super"], "Semi")
        self.assertEqual(items["missile_size"], 10)
        self.assertIsNone(items["preset"])

    def test_item_pool_preset_relabel(self):
        s = build(item_pool_preset="reduced")
        self.assertEqual(s["item_progression_settings"]["item_pool_preset"], "Reduced")
        s = build(starting_items_preset="all")
        self.assertEqual(s["item_progression_settings"]["starting_items_preset"], "All")

    def test_objectives(self):
        s = build(objectives_preset="none", objective_kraid="yes", objective_plasma_room="maybe", min_objectives=1,
                  max_objectives=2)
        obj = s["objective_settings"]
        options = {e["objective"]: e["setting"] for e in obj["objective_options"]}
        self.assertEqual(options["Kraid"], "Yes")
        self.assertEqual(options["PlasmaRoom"], "Maybe")
        self.assertEqual((obj["min_objectives"], obj["max_objectives"]), (1, 2))
        self.assertIsNone(obj["preset"])

    def test_other_settings(self):
        s = build(map_layout="wild", save_animals="randomized", wall_jump="collectible", speed_booster="split",
                  start_location="randomized", doors_preset="beam", plasma_doors_count=5, savestate="limited",
                  energy_free_shinesparks="true", door_locks_size="small")
        self.assertEqual(s["map_layout"], "Wild")
        self.assertEqual(s["save_animals"], "Random")
        self.assertEqual(s["other_settings"]["wall_jump"], "Collectible")
        self.assertEqual(s["other_settings"]["speed_booster"], "Split")
        self.assertEqual(s["other_settings"]["savestate"], "Limited")
        self.assertTrue(s["other_settings"]["energy_free_shinesparks"])
        self.assertEqual(s["other_settings"]["door_locks_size"], "Small")
        self.assertEqual(s["start_location_settings"]["mode"], "Random")
        self.assertEqual(s["doors_settings"]["plasma_doors_count"], 5)
        self.assertIsNone(s["doors_settings"]["preset"])

    def test_custom_start_location(self):
        s = build(start_location="custom", custom_start_location="bomb torizo room")
        self.assertEqual(s["start_location_settings"], {"mode": "Custom", "room_id": 19, "node_id": 1})

    def test_map_rando_settings_json(self):
        exported = load_preset("full-settings", "Mentor Tournament")
        exported["name"] = "My Settings"
        exported["map_layout"] = "Small"
        s = build(map_rando_settings=exported, fast_doors="false")
        self.assertEqual(s["map_layout"], "Small")
        self.assertFalse(s["quality_of_life_settings"]["fast_doors"])
        self.assertEqual(s["skill_assumption_settings"]["preset"], "Medium")

    def test_validated_by_map_rando(self):
        from .. import native
        for kwargs in [{}, {"settings_preset": "community_race_season_5"}, {"skill_assumptions_preset": "insane_plus",
                       "item_progression_preset": "desolate", "quality_of_life_preset": "off"},
                       {"crash_fixes": "crash", "item_pool": {"ETank": 30}}]:
            with self.subTest(**{k: str(v) for k, v in kwargs.items()}):
                s = build(**kwargs)
                upgraded = native.upgrade_settings(s)
                self.assertEqual(canonical(without(upgraded, "version", "name")),
                                 canonical(without(s, "version", "name")))


class TestCustomize(unittest.TestCase):
    def test_defaults(self):
        c = settings_builder.build_customize_settings(make_world())
        self.assertEqual(c["tile_theme"], "area_themed")
        self.assertEqual(c["room_palettes"], "vanilla")
        self.assertEqual(c["etank_color"], "de3894")
        self.assertEqual(c["spin_lock_buttons"], ["L", "R", "Up", "X"])

    def test_values(self):
        c = settings_builder.build_customize_settings(make_world(
            room_theming="palettes", tile_theme="wrecked_ship", etank_color="ff0000", samus_sprite="samus_dread",
            screw_attack_animation="vanilla", control_shot="y", moonwalk=True))
        self.assertEqual(c["room_palettes"], "area-themed")
        self.assertEqual(c["tile_theme"], "WreckedShip")
        self.assertEqual(c["etank_color"], "ff0000")
        self.assertEqual(c["samus_sprite"], "samus_dread")
        self.assertTrue(c["vanilla_screw_attack_animation"])
        self.assertEqual(c["control_shot"], "Y")
        self.assertTrue(c["moonwalk"])


class TestUpstreamConsistency(unittest.TestCase):
    """Checks that hand-written parts of the world agree with Map Rando's data (these fail when upstream changes)."""

    def test_items_match_map_rando(self):
        from ..Items import ITEM_DATA
        self.assertEqual([d.rando_name for d in ITEM_DATA], settings_builder.PRESETS_INDEX["items"])

    def test_sub_preset_rules_match_preset_files(self):
        for group, presets in settings_builder.config_sub_presets().items():
            rule = settings_builder.SUB_PRESETS[group][0]
            for name, definition in presets.items():
                with self.subTest(group=group, preset=name):
                    self.assertEqual(canonical(rule(name)), canonical(definition))

    def test_sub_preset_names_known(self):
        for group, presets in settings_builder.config_sub_presets().items():
            for name in presets:
                self.assertIn(name, settings_builder.SUB_PRESETS[group][1], group)
