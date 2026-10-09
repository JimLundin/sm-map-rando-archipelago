"""The engine for the repository's tools and tests: the `smmr_engine` module `uv sync` builds into the environment,
with Map Rando's data from the MapRandomizer checkout (or `SMMR_DATA`) and map pools from `SMMR_MAPS`."""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "world" / "smmr"))   # `core` alone: importing `smmr` needs Archipelago

from core.engine import NativeEngine  # noqa: E402


@lru_cache(maxsize=None)
def local_engine() -> NativeEngine:
    import smmr_engine
    maps = os.environ.get("SMMR_MAPS")
    return NativeEngine(smmr_engine, Path(os.environ.get("SMMR_DATA", ROOT / "MapRandomizer")),
                        Path(maps) if maps else None)
