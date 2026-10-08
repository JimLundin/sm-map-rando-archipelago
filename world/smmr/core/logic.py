"""Stage S3: a Seed's logic, as Archipelago-shaped data.

Map Rando's spoiler summary lists the steps in which its item placement collected items. The locations of step *k*
are reachable with every item collected in steps 1..k-1 (that is how Map Rando placed them), so step *k* becomes a
region requiring those items. The rule is sound by construction, and it needs nothing from Map Rando's logic itself.

Locations Map Rando didn't place progression in (after "stop item placement early", or with an escape start) are in
a final region requiring everything, and only get filler.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Tuple

from .catalog import Catalog

PROGRESSION, USEFUL, FILLER = "progression", "useful", "filler"


@dataclass(frozen=True)
class Step:
    number: int
    locations: Tuple[int, ...]       # item location indexes
    requires: Mapping[str, int]      # Archipelago item name → count, of our own items


@dataclass(frozen=True)
class PoolItem:
    name: str
    classification: str
    step: int                        # the step whose locations Map Rando put it in (len(steps) + 1: none)


@dataclass(frozen=True)
class LogicModel:
    steps: Tuple[Step, ...]
    remaining: Step                  # locations outside the steps; excluded from progression when there are steps
    pool: Tuple[PoolItem, ...]       # one item per item location, in location index order


def build_logic(seed: Mapping[str, Any], catalog: Catalog) -> LogicModel:
    summary: List[Dict[str, Any]] = [step for step in seed["spoiler"]["summary"] if step["items"]]
    placement: List[str] = seed["randomization"]["item_placement"]

    steps = []
    step_of: Dict[int, int] = {}
    collected: Counter = Counter()
    for number, step in enumerate(summary, start=1):
        locations = []
        for entry in step["items"]:
            location = catalog.location_at(entry["location"]["room_id"], entry["location"]["node_id"])
            locations.append(location.index)
            step_of[location.index] = number
        steps.append(Step(number, tuple(locations), dict(collected)))
        for entry in step["items"]:
            if entry["item"] != "Nothing":
                collected[catalog.item(entry["item"]).name] += 1

    final = len(steps) + 1
    remaining = Step(final, tuple(loc.index for loc in catalog.locations if loc.index not in step_of),
                     dict(collected))

    pool = []
    for location in catalog.locations:
        kind = catalog.item(placement[location.index])
        if kind.rando_name == "Nothing":
            classification = FILLER
        elif location.index in step_of:
            classification = PROGRESSION
        elif not steps and (kind.unique or kind.rando_name in ("ETank", "ReserveTank")):
            classification = USEFUL   # escape start: nothing is needed, but upgrades are still worth having
        else:
            classification = FILLER   # placed outside Map Rando's logic: only filler locations can take it
        pool.append(PoolItem(kind.name, classification, step_of.get(location.index, final)))
    return LogicModel(tuple(steps), remaining, tuple(pool))
