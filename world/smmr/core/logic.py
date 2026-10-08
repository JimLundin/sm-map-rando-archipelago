"""Stage S3: the logic, Map Rando's own, through the engine's `reach` (docs/specs/logic-oracle.md).

A location's rule asks the oracle what the items of ours collected so far (with the starting items) make reachable:
the oracle runs Map Rando's traversal, and answers are cached by the items' counts. How it answers is the engine's
business: a fresh traversal per inventory for now.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeAlias

from .catalog import Catalog

Inventory: TypeAlias = Mapping[str, int]                  # Map Rando item name → count
InventoryKey: TypeAlias = tuple[tuple[str, int], ...]


class Classification(StrEnum):
    PROGRESSION = "progression"
    PROGRESSION_SKIP_BALANCING = "progression_skip_balancing"   # tanks and ammo: the logic counts them
    USEFUL = "useful"
    FILLER = "filler"


@dataclass(frozen=True, slots=True)
class Reach:
    locations: frozenset[int]        # item location indexes Samus can reach and come back from
    beatable: bool                   # Mother Brain can be defeated


Query: TypeAlias = Callable[[Sequence[Inventory]], list[Reach]]


@dataclass(slots=True)
class Oracle:
    """What our collected items make reachable. `query` answers a batch of inventories, e.g. the engine's `reach`
    with a session."""
    query: Query
    _cache: dict[InventoryKey, Reach] = field(default_factory=dict[InventoryKey, Reach])
    queries: int = 0

    def reach(self, counts: Inventory) -> Reach:
        key = tuple(sorted((item, count) for item, count in counts.items() if count))
        reach = self._cache.get(key)
        if reach is None:
            self.queries += 1
            [reach] = self.query([dict(key)])
            self._cache[key] = reach
        return reach


@dataclass(frozen=True, slots=True)
class PoolItem:
    name: str                        # Archipelago name
    classification: Classification


def classify(rando_name: str, catalog: Catalog) -> Classification:
    """Every item the logic knows is progression (it counts tanks and ammo too); Nothing is filler."""
    if rando_name == "Nothing":
        return Classification.FILLER
    if catalog.item(rando_name).unique:
        return Classification.PROGRESSION
    return Classification.PROGRESSION_SKIP_BALANCING


def item_pool(pool: Mapping[str, int], catalog: Catalog) -> list[PoolItem]:
    """The items Map Rando would place (the engine's `world` pool)."""
    return [PoolItem(catalog.item(rando_name).name, classify(rando_name, catalog))
            for rando_name, count in pool.items() for _ in range(count)]
