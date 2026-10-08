from conftest import load_json
from core.options import build_settings


def test_overridden_settings_are_no_longer_the_named_preset():
    preset = load_json("world/smmr/data/presets.json")["Default"]
    settings = build_settings(preset, "Vanilla", seed=7)
    assert settings["name"] is None   # else Map Rando's upgrade would re-apply the preset over map_layout
    assert settings["map_layout"] == "Vanilla"
    assert settings["other_settings"]["random_seed"] == 7
    assert preset["name"] == "Default" and preset["map_layout"] == "Standard"   # the preset is untouched
