"""The logic oracle against Map Rando's own placement, across random settings on the vanilla map.

For each random combination of presets, Map Rando places items (`randomize`); `reach`, given the items of its steps
before k, must make exactly the locations of its steps up to k reachable (locations holding Nothing aside: the
Desolate pool's steps omit them). It also checks that more items never lose a location.

    python tools/check_reach.py [random seed] [number of settings]      # CHAIN=1: continue the traversal
    python tools/check_reach.py <saved mismatch .json>                   # re-check one

Mismatches are saved to /tmp/smmr-reach-mismatch-<n>.json. Known: in a few percent of seeds, Map Rando's traversal
(at most four states per vertex) finds a location one step earlier or later than a fresh traversal does, and more
items can lose a location; with CHAIN=1 (Map Rando's own way) every seed agrees.
"""
import json, random, sys, time
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "world/smmr")]
from core.catalog import Catalog
from core.engine import SubprocessEngine
from core.options import OptionValues, build_settings

import os
CHAIN = bool(os.environ.get('CHAIN'))
catalog = Catalog.from_info(json.loads((ROOT / "world/smmr/data/info.json").read_text()))
presets = json.loads((ROOT / "world/smmr/data/presets.json").read_text())
cats = json.loads((ROOT / "world/smmr/data/info.json").read_text())["category_presets"]
engine = SubprocessEngine(ROOT / "engine/target/dev-release/smmr-engine", ROOT / "MapRandomizer")

def check(settings, seed_artifact):
    r = seed_artifact["randomization"]
    world = {k: r[k] for k in ("map", "locked_doors", "objectives", "start_location", "save_animals",
                                "escape_time_seconds", "toilet_intersections", "seed", "display_seed")}
    world["hub"] = seed_artifact["spoiler"]["hub"]
    steps = [s for s in seed_artifact["spoiler"]["summary"] if s["items"]]
    inventories, expected, have, seen = [], [], Counter(), set()
    for s in steps:
        inventories.append(dict(have))
        for e in s["items"]:
            seen.add(catalog.location_at(e["location"]["room_id"], e["location"]["node_id"]).index)
            if e["item"] != "Nothing":
                have[e["item"]] += 1
        expected.append(set(seen))
    inventories.append(dict(have))
    results = engine.call("reach", {"settings": settings, "world": world, "inventories": inventories, "chain": CHAIN})
    problems = []
    real = {i for i, item in enumerate(r["item_placement"]) if item != "Nothing"}   # Desolate's steps omit Nothing
    for k, (res, exp) in enumerate(zip(results, expected), start=1):
        got, exp = set(res["locations"]) & real, exp & real
        if exp - got: problems.append(f"step {k}: missing {sorted(exp - got)}")
        if got - exp: problems.append(f"step {k}: extra {sorted(got - exp)}")
    for k in range(1, len(results)):   # monotone: more items never lose a location
        lost = set(results[k - 1]["locations"]) - set(results[k]["locations"])
        if lost:
            problems.append(f"NOT MONOTONE at {k}: lost {sorted(lost)}")
    return problems, len(steps), results[-1]["beatable"]

if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):
    d = json.loads(Path(sys.argv[1]).read_text())
    print(check(d["settings"], d["seed"])); sys.exit()
rng = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
n = int(sys.argv[2]) if len(sys.argv) > 2 else 16
fails = 0
for i in range(n):
    values = OptionValues(
        preset=rng.choice(list(presets)), map_layout="Vanilla",
        categories={"skill_assumptions": rng.choice(["Basic", "Medium", "Hard", "Expert", "Insane"]),
                    "item_progression": rng.choice(["Normal", "Tricky", "Technical", "Challenge", "Desolate"]),
                    "doors": rng.choice(cats["doors_settings"]),
                    "objectives": rng.choice(["Bosses", "Minibosses", "Chozos", "Pirates", "Metroids", "Random"]),
                    "quality_of_life": rng.choice(["Low", "Default", "Max"])},
        start_location=rng.choice(["Ship", "Random"]), wall_jump=rng.choice(["Vanilla", "Collectible"]))
    settings = engine.upgrade(build_settings(presets, values, rng.getrandbits(32)))
    seed = rng.getrandbits(32)
    t = time.time()
    try:
        artifact = engine.randomize(settings, seed)
    except Exception as e:
        print(f"{i:2} randomize failed: {e}"); continue
    problems, steps, beatable = check(settings, artifact)
    desc = f"{values.preset[:12]:12} {values.categories['skill_assumptions']:7} {values.categories['item_progression']:9} {values.categories['doors']:5} {values.categories['objectives']:10} {values.start_location:6} wj={values.wall_jump}"
    print(f"{i:2} {desc}  steps={steps:2} beatable={beatable} {'OK' if not problems else 'MISMATCH ' + '; '.join(problems)}  ({time.time() - t:.0f}s)")
    fails += bool(problems)
    if problems:
        Path(f"/tmp/smmr-reach-mismatch-{i}.json").write_text(json.dumps({"settings": settings, "seed": artifact}))
print(f"{n - fails}/{n} agree")
