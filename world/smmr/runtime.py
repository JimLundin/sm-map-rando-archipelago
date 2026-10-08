"""Where the engine and its data are on this machine.

Development: `SMMR_ENGINE` (the binary) and `SMMR_DATA` (a MapRandomizer checkout with `tools/fetch_data.py` run),
defaulting to the repository's build outputs. Releases bundle both in the .apworld (milestone 7).
"""
from __future__ import annotations

import json
import os
import pkgutil
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from .core.abi import Abi
from .core.catalog import Catalog
from .core.engine import SubprocessEngine

REPO = Path(__file__).resolve().parents[2]


def data(name: str) -> bytes:
    """A file in the world's data/ (works from a zipped .apworld too)."""
    content = pkgutil.get_data(__package__, f"data/{name}")
    assert content is not None
    return content


@lru_cache(maxsize=None)
def engine() -> SubprocessEngine:
    binary = Path(os.environ.get("SMMR_ENGINE", REPO / "engine/target/dev-release/smmr-engine"))
    data = Path(os.environ.get("SMMR_DATA", REPO / "MapRandomizer"))
    maps = os.environ.get("SMMR_MAPS")
    return SubprocessEngine(binary, data, Path(maps) if maps else None)


@lru_cache(maxsize=None)
def catalog() -> Catalog:
    return Catalog.from_info(json.loads(data("info.json")))


@lru_cache(maxsize=None)
def abi() -> Abi:
    return Abi.parse(data("abi.toml").decode())


def preset(name: str) -> Dict[str, Any]:
    return json.loads(data("presets.json"))[name]
