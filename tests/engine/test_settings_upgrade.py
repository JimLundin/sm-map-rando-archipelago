"""S1's settings through the real engine's upgrade: every option value is settings Map Rando accepts, and the
upgraded settings are what the option asked for. Needs the engine build (`make engine`)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "world" / "smmr"))

from core.engine import SubprocessEngine  # noqa: E402
from core.options import CATEGORIES, START_LOCATIONS, WALL_JUMP, OptionValues, build_settings  # noqa: E402

BINARY = ROOT / "engine/target/dev-release/smmr-engine"
PRESETS = json.loads((ROOT / "world/smmr/data/presets.json").read_text())
INFO = json.loads((ROOT / "world/smmr/data/info.json").read_text())

pytestmark = pytest.mark.skipif(not BINARY.exists(), reason="needs the engine build (make engine)")


@pytest.fixture(scope="module")
def engine():
    return SubprocessEngine(BINARY, ROOT / "MapRandomizer")


@pytest.mark.parametrize("option, field", CATEGORIES.items())
def test_every_category_preset_upgrades_to_itself(engine, option, field):
    for name in INFO["category_presets"][field]:
        upgraded = engine.upgrade(build_settings(PRESETS, OptionValues("Default", categories={option: name}), 1))
        assert upgraded[field]["preset"] == name


def test_every_full_preset_and_single_setting_upgrades(engine):
    for preset in PRESETS:
        for start, wall_jump in zip(START_LOCATIONS, WALL_JUMP * 2):
            values = OptionValues(preset, "Vanilla", start_location=start, wall_jump=wall_jump)
            upgraded = engine.upgrade(build_settings(PRESETS, values, 1))
            assert upgraded["start_location_settings"]["mode"] == start
            assert upgraded["other_settings"]["wall_jump"] == wall_jump
            assert upgraded["map_layout"] == "Vanilla"
