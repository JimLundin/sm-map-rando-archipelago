"""The engine port: the only way the world calls Map Rando.

`NativeEngine` calls `smmr_engine`, our PyO3 module over Map Rando (engine/src/lib.rs, its types in
smmr_engine.pyi). `runtime` imports the module (from the development install, or extracted from the .apworld) and
passes it in, so the core doesn't import it. Map Rando's own data crosses as JSON; the logic's queries don't.
"""
from __future__ import annotations

import json
import platform
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Protocol, Self

from .logic import Inventory, Reach

if TYPE_CHECKING:
    import smmr_engine

type JsonObject = dict[str, Any]      # Map Rando's own data (settings, a world): only the engine reads it


@dataclass(frozen=True, slots=True)
class GeneratedWorld:
    """The engine's `world`: everything but the item placement."""
    world: JsonObject                        # given back to the engine as it is (`open`, `rom`)
    seed_hash: str
    pool: dict[str, int]                     # the items to place: Map Rando item name → count
    locations: list[int]                     # the item locations in the map's rooms
    starting_items: dict[str, int]
    escape: bool                             # Samus starts in the escape with every item: nothing to place

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Self:
        return cls(data["world"], data["seed_hash"], dict(data["pool"]), list(data["locations"]),
                   {item: count for item, count in data["starting_items"].items() if count}, data["escape"])


def platform_tag() -> str:
    """Names the engine build for this machine in the .apworld's bin/ (e.g. linux-x86_64, win32-amd64)."""
    return f"{sys.platform}-{platform.machine().lower()}"


class EngineError(Exception):
    """Map Rando rejected the request (invalid settings, randomization failed, ...)."""


class WorldLogic(Protocol):
    def reach(self, inventories: Sequence[Inventory]) -> list[Reach]:
        """For each inventory (on top of the starting items), what it makes reachable."""
        ...


class Engine(Protocol):
    def info(self) -> JsonObject: ...

    def upgrade(self, settings: Mapping[str, Any]) -> JsonObject: ...

    def randomize(self, settings: Mapping[str, Any], seed: int) -> JsonObject: ...

    def world(self, settings: Mapping[str, Any], seed: int) -> GeneratedWorld: ...

    def open(self, settings: Mapping[str, Any], world: JsonObject) -> WorldLogic: ...

    def rom(self, settings: Mapping[str, Any], randomization: JsonObject, rom: Path, out: Path) -> None: ...

    def rom_from_world(self, settings: Mapping[str, Any], world: JsonObject, item_placement: Sequence[str],
                       foreign_items: Sequence[Mapping[str, Any]], rom: Path, out: Path) -> None: ...


@dataclass(frozen=True, slots=True)
class NativeWorldLogic:
    session: smmr_engine.Session

    def reach(self, inventories: Sequence[Inventory]) -> list[Reach]:
        answers = self.session.reach([dict(inventory) for inventory in inventories])
        return [Reach(frozenset(locations), beatable) for locations, beatable in answers]


class NativeEngine:
    """The port over `smmr_engine` (passed in by `runtime`): Map Rando's data from `data_dir`, map pools from
    `maps_dir` (default `data_dir/maps`)."""

    def __init__(self, module: ModuleType, data_dir: Path, maps_dir: Path | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.maps_dir = Path(maps_dir) if maps_dir is not None else None
        self._error: type[Exception] = module.EngineError
        self._engine: smmr_engine.Engine = self._call(lambda: module.Engine.load(self.data_dir))

    def _call[T](self, f: Callable[[], T]) -> T:
        try:
            return f()
        except self._error as e:
            raise EngineError(str(e)) from e

    def info(self) -> JsonObject:
        return json.loads(self._call(self._engine.info))

    def upgrade(self, settings: Mapping[str, Any]) -> JsonObject:
        return json.loads(self._call(lambda: self._engine.upgrade(json.dumps(settings))))

    def randomize(self, settings: Mapping[str, Any], seed: int) -> JsonObject:
        return json.loads(self._call(lambda: self._engine.randomize(json.dumps(settings), seed, self.maps_dir)))

    def world(self, settings: Mapping[str, Any], seed: int) -> GeneratedWorld:
        answer = self._call(lambda: self._engine.world(json.dumps(settings), seed, self.maps_dir))
        return GeneratedWorld.from_json(json.loads(answer))

    def open(self, settings: Mapping[str, Any], world: JsonObject) -> WorldLogic:
        """The world's logic, set up once for many `reach` queries."""
        return NativeWorldLogic(self._call(lambda: self._engine.open(json.dumps(settings), json.dumps(world))))

    def reach_unsessioned(self, request: JsonObject) -> list[JsonObject]:
        """`reach` with the settings and the world in the request (`{settings, world, inventories, chain?}`)."""
        return json.loads(self._call(lambda: self._engine.reach(json.dumps(request))))

    def rom(self, settings: Mapping[str, Any], randomization: JsonObject, rom: Path, out: Path) -> None:
        self._rom({"settings": settings, "randomization": randomization, "rom": rom, "out": out})

    def rom_from_world(self, settings: Mapping[str, Any], world: JsonObject, item_placement: Sequence[str],
                       foreign_items: Sequence[Mapping[str, Any]], rom: Path, out: Path) -> None:
        self._rom({"settings": settings, "world": world, "item_placement": list(item_placement),
                   "foreign_items": list(foreign_items), "rom": rom, "out": out})

    def _rom(self, request: dict[str, Any]) -> None:
        request = {**request, "rom": str(Path(request["rom"]).resolve()), "out": str(Path(request["out"]).resolve())}
        self._call(lambda: self._engine.rom(json.dumps(request)))
