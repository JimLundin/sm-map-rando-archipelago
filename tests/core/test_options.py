from conftest import load_json
from core.options import OptionValues, build_settings, option_key

PRESETS = load_json("world/smmr/data/presets.json")


def test_overridden_settings_are_no_longer_the_named_preset():
    settings = build_settings(PRESETS, OptionValues("Default", "Vanilla"), seed=7)
    assert settings["name"] is None   # else Map Rando's upgrade would re-apply the preset over map_layout
    assert settings["map_layout"] == "Vanilla"
    assert settings["other_settings"]["random_seed"] == 7
    assert PRESETS["Default"]["name"] == "Default" and PRESETS["Default"]["map_layout"] == "Standard"


def test_a_category_is_chosen_by_its_preset_name():
    settings = build_settings(PRESETS, OptionValues("Default", categories={"skill_assumptions": "Expert",
                                                                           "doors": None}), seed=1)
    assert settings["skill_assumption_settings"]["preset"] == "Expert"
    assert settings["doors_settings"] == PRESETS["Default"]["doors_settings"]   # None: the full preset's


def test_option_keys():
    assert [option_key(n) for n in ("Very Hard", "Expert+", "Community Race Season 5", "Random")] == \
        ["very_hard", "expert_plus", "community_race_season_5", "randomized"]
