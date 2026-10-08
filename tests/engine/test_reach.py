"""The world and the logic oracle (`world`, `reach`, `rom` from a world) through the real engine. `reach` must agree
with Map Rando's own placement: the locations of step k are reachable with the items of the steps before it, and no
others. Needs the engine build (`make engine`); the ROM test also SMMR_TEST_ROM. Broader runs: tools/check_reach.py.
"""
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "world" / "smmr"))

from core.catalog import Catalog  # noqa: E402
from core.engine import SubprocessEngine  # noqa: E402

BINARY = ROOT / "engine/target/dev-release/smmr-engine"
SETTINGS = json.loads((ROOT / "fixtures/settings/default-vanilla.upgraded.json").read_text())
SEED = json.loads((ROOT / "fixtures/seeds/default-vanilla-1.json").read_text())
SHIP_HUB = [8, 5]
WORLD_FIELDS = ("map", "locked_doors", "objectives", "start_location", "save_animals", "escape_time_seconds",
                "toilet_intersections", "seed", "display_seed")

pytestmark = pytest.mark.skipif(not BINARY.exists(), reason="needs the engine build (make engine)")


@pytest.fixture(scope="module")
def engine():
    return SubprocessEngine(BINARY, ROOT / "MapRandomizer")


@pytest.fixture(scope="module")
def catalog():
    return Catalog.from_info(json.loads((ROOT / "world/smmr/data/info.json").read_text()))


def world_of(seed):
    """A seed's world: its randomization without the item placement."""
    world = {field: seed["randomization"][field] for field in WORLD_FIELDS}
    world["hub"] = seed["spoiler"].get("hub", SHIP_HUB)
    return world


def test_reach_agrees_with_map_randos_placement_step_by_step(engine, catalog):
    steps = [step for step in SEED["spoiler"]["summary"] if step["items"]]
    inventories, expected, have, seen = [], [], Counter(), set()
    for step in steps:
        inventories.append(dict(have))
        for entry in step["items"]:
            seen.add(catalog.location_at(entry["location"]["room_id"], entry["location"]["node_id"]).index)
            if entry["item"] != "Nothing":
                have[entry["item"]] += 1
        expected.append(set(seen))
    inventories.append(dict(have))
    results = engine.call("reach", {"settings": SETTINGS, "world": world_of(SEED), "inventories": inventories})
    for k, (result, locations) in enumerate(zip(results, expected), start=1):
        assert set(result["locations"]) == locations, f"step {k}"
    assert results[-1]["beatable"] and len(results[-1]["locations"]) == 100
    assert not results[0]["beatable"]


def test_world_is_a_world_items_can_be_placed_in(engine):
    world = engine.call("world", {"settings": SETTINGS, "seed": 7})["world"]
    nothing, everything = engine.call("reach", {"settings": SETTINGS, "world": world, "inventories": [
        {}, {"Morph": 1, "Bombs": 1, "Charge": 1, "Ice": 1, "Wave": 1, "Spazer": 1, "Plasma": 1, "Varia": 1,
             "Gravity": 1, "SpaceJump": 1, "ScrewAttack": 1, "SpeedBooster": 1, "HiJump": 1, "SpringBall": 1,
             "Grapple": 1, "XRayScope": 1, "Missile": 46, "Super": 10, "PowerBomb": 10, "ETank": 14,
             "ReserveTank": 4}]})
    assert nothing["locations"] and not nothing["beatable"]
    assert everything["beatable"]
    assert engine.call("world", {"settings": SETTINGS, "seed": 7})["world"] == world   # deterministic


@pytest.mark.skipif(not os.environ.get("SMMR_TEST_ROM"), reason="needs SMMR_TEST_ROM")
def test_a_rom_builds_from_a_world_and_a_placement(engine):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.sfc"
        engine.call("rom", {"settings": SETTINGS, "world": world_of(SEED),
                            "item_placement": SEED["randomization"]["item_placement"], "foreign_items": [],
                            "rom": os.environ["SMMR_TEST_ROM"], "out": str(out)})
        assert out.stat().st_size == 0x400000
