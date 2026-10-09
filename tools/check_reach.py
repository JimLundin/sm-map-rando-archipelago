"""The logic oracle against Map Rando's own placement, across random settings on the vanilla map.

For each random combination of presets, Map Rando places items (`randomize`); `reach`, given the items of its steps
before k, must make exactly the locations of its steps up to k reachable (locations holding Nothing aside: the
Desolate pool's steps omit them). It also checks that more items never lose a location.

    uv run tools/check_reach.py [random seed] [number of settings]      # CHAIN=1: continue the traversal
    uv run tools/check_reach.py <saved mismatch .json>                   # re-check one

Mismatches are saved to /tmp/smmr-reach-mismatch-<n>.json. Known: in a few percent of seeds, Map Rando's traversal
(at most four states per vertex) finds a location one step earlier or later than a fresh traversal does, and more
items can lose a location; with CHAIN=1 (Map Rando's own way) every seed agrees.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "world/smmr")]

from core.catalog import Catalog  # noqa: E402
from core.engine import JsonObject, NativeEngine  # noqa: E402
from local_engine import local_engine  # noqa: E402
from core.options import OptionValues, build_settings  # noqa: E402

CHAIN = bool(os.environ.get("CHAIN"))
WORLD_FIELDS = ("map", "locked_doors", "objectives", "start_location", "save_animals", "escape_time_seconds",
                "toilet_intersections", "seed", "display_seed")


@dataclass(frozen=True, slots=True)
class Missing:
    """Map Rando reached these at the step; the oracle didn't (it's stricter there)."""
    step: int
    locations: frozenset[int]


@dataclass(frozen=True, slots=True)
class Extra:
    """The oracle reached these at the step; Map Rando didn't yet."""
    step: int
    locations: frozenset[int]


@dataclass(frozen=True, slots=True)
class Lost:
    """More items lost these locations: the oracle isn't monotone there."""
    step: int
    locations: frozenset[int]


type Mismatch = Missing | Extra | Lost


def describe(mismatch: Mismatch) -> str:
    match mismatch:
        case Missing(step, locations):
            return f"step {step}: missing {sorted(locations)}"
        case Extra(step, locations):
            return f"step {step}: extra {sorted(locations)}"
        case Lost(step, locations):
            return f"NOT MONOTONE at {step}: lost {sorted(locations)}"
        case _:
            assert_never(mismatch)


def check(engine: NativeEngine, catalog: Catalog, settings: JsonObject, seed: JsonObject) -> list[Mismatch]:
    """`reach` against the steps of Map Rando's placement in `seed` (the engine's `randomize`)."""
    randomization = seed["randomization"]
    world = {field: randomization[field] for field in WORLD_FIELDS} | {"hub": seed["spoiler"]["hub"]}
    steps = [step for step in seed["spoiler"]["summary"] if step["items"]]
    inventories: list[dict[str, int]] = []
    expected: list[frozenset[int]] = []
    have: Counter[str] = Counter()
    seen: set[int] = set()
    for step in steps:
        inventories.append(dict(have))
        for entry in step["items"]:
            seen.add(catalog.location_at(entry["location"]["room_id"], entry["location"]["node_id"]).index)
            if entry["item"] != "Nothing":
                have[entry["item"]] += 1
        expected.append(frozenset(seen))
    inventories.append(dict(have))
    request = {"settings": settings, "world": world, "inventories": inventories, "chain": CHAIN}
    answers = engine.reach_unsessioned(request)
    real = frozenset(i for i, item in enumerate(randomization["item_placement"]) if item != "Nothing")
    reached = [frozenset(answer["locations"]) for answer in answers]
    mismatches: list[Mismatch] = []
    for k, (got, want) in enumerate(zip(reached, expected), start=1):
        got, want = got & real, want & real
        if want - got:
            mismatches.append(Missing(k, want - got))
        if got - want:
            mismatches.append(Extra(k, got - want))
    for k in range(1, len(reached)):
        if lost := reached[k - 1] - reached[k]:
            mismatches.append(Lost(k, lost))
    return mismatches


def random_values(rng: random.Random, presets: list[str], doors: list[str]) -> OptionValues:
    return OptionValues(
        preset=rng.choice(presets), map_layout="Vanilla",
        categories={"skill_assumptions": rng.choice(["Basic", "Medium", "Hard", "Expert", "Insane"]),
                    "item_progression": rng.choice(["Normal", "Tricky", "Technical", "Challenge", "Desolate"]),
                    "doors": rng.choice(doors),
                    "objectives": rng.choice(["Bosses", "Minibosses", "Chozos", "Pirates", "Metroids", "Random"]),
                    "quality_of_life": rng.choice(["Low", "Default", "Max"])},
        start_location=rng.choice(["Ship", "Random"]), wall_jump=rng.choice(["Vanilla", "Collectible"]))


def main() -> None:
    info = json.loads((ROOT / "world/smmr/data/info.json").read_text())
    catalog = Catalog.from_info(info)
    presets: dict[str, JsonObject] = json.loads((ROOT / "world/smmr/data/presets.json").read_text())
    engine = local_engine()
    if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):
        saved = json.loads(Path(sys.argv[1]).read_text())
        print([describe(m) for m in check(engine, catalog, saved["settings"], saved["seed"])])
        return
    rng = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    agree = 0
    for i in range(count):
        values = random_values(rng, list(presets), info["category_presets"]["doors_settings"])
        settings = engine.upgrade(build_settings(presets, values, rng.getrandbits(32)))
        started = time.time()
        try:
            seed = engine.randomize(settings, rng.getrandbits(32))
        except Exception as e:
            print(f"{i:2} randomize failed: {e}")
            continue
        mismatches = check(engine, catalog, settings, seed)
        steps = sum(1 for step in seed["spoiler"]["summary"] if step["items"])
        label = (f"{values.preset[:12]:12} {values.categories['skill_assumptions']:7} "
                 f"{values.categories['item_progression']:9} {values.categories['doors']:5} "
                 f"{values.categories['objectives']:10} {values.start_location:6} wj={values.wall_jump}")
        verdict = "; ".join(describe(m) for m in mismatches) or "OK"
        print(f"{i:2} {label}  steps={steps:2} {verdict}  ({time.time() - started:.0f}s)")
        if mismatches:
            Path(f"/tmp/smmr-reach-mismatch-{i}.json").write_text(json.dumps({"settings": settings, "seed": seed}))
        else:
            agree += 1
    print(f"{agree}/{count} agree")


if __name__ == "__main__":
    main()
