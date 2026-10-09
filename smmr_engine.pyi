"""Map Rando (our fork) as a Python module, for the Archipelago world. See engine/src/lib.rs; the world's port is
world/smmr/core/engine.py. Map Rando's own data (settings, worlds, randomizations) is JSON text."""
from os import PathLike


class EngineError(Exception):
    """Map Rando rejected the request (invalid settings, randomization failed, ...)."""


class Engine:
    @staticmethod
    def load(data_dir: str | PathLike[str]) -> Engine:
        """Map Rando's data from `data_dir` (a MapRandomizer checkout, or the data the .apworld bundles), loaded once
        per process."""

    def info(self) -> str: ...
    def upgrade(self, settings: str) -> str: ...
    def randomize(self, settings: str, seed: int, maps_dir: str | PathLike[str] | None = None) -> str: ...
    def world(self, settings: str, seed: int, maps_dir: str | PathLike[str] | None = None) -> str: ...
    def open(self, settings: str, world: str) -> Session: ...

    def reach(self, request: str) -> str:
        """`reach` without a session: `{settings, world, inventories, chain?}` (tools/check_reach.py)."""

    def rom(self, request: str) -> None:
        """Writes Map Rando's ROM: `{settings, randomization, rom, out}` or `{settings, world, item_placement,
        foreign_items, rom, out}`."""


class Session:
    def reach(self, inventories: list[dict[str, int]]) -> list[tuple[list[int], bool]]:
        """For each inventory (Map Rando item → count, on top of the starting items): the item locations Samus can
        reach and come back from, and whether she can defeat Mother Brain."""
