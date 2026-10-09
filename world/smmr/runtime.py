"""Where the engine (`smmr_engine`, our PyO3 module over Map Rando) and its data are on this machine.

- Development (the world runs from the repository, e.g. symlinked into Archipelago): the module installed in the
  Python environment (`uv sync` builds it), and `SMMR_DATA` (a MapRandomizer checkout with `tools/fetch_data.py` run),
  defaulting to the repository's.
- Release: the .apworld bundles the module for each platform (`bin/<platform>/`) and Map Rando's data
  (`data/engine-data.zip`, see tools/build_apworld.py). A native module can't load from a zip, so they are extracted
  to Archipelago's cache on first use, into a directory named by their hash: a new release never runs an old copy.
"""
from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pkgutil
import sys
import zipfile
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

from .core.abi import Abi
from .core.catalog import Catalog
from .core.engine import NativeEngine, platform_tag

REPO = Path(__file__).resolve().parents[2]


def data(name: str) -> bytes:
    """A file in the world's data/ (works from a zipped .apworld too)."""
    content = pkgutil.get_data(__name__.rpartition(".")[0], f"data/{name}")
    assert content is not None
    return content


def _bundled(name: str) -> bytes | None:
    try:
        return pkgutil.get_data(__name__.rpartition(".")[0], name)
    except OSError:
        return None


MODULE_FILE = "smmr_engine.pyd" if sys.platform == "win32" else "smmr_engine.abi3.so"


@lru_cache(maxsize=None)
def engine() -> NativeEngine:
    """This machine's engine, loaded once per process."""
    maps = os.environ.get("SMMR_MAPS")
    maps_dir = Path(maps) if maps else None
    if (REPO / "engine").is_dir():
        import smmr_engine
        return NativeEngine(smmr_engine, Path(os.environ.get("SMMR_DATA", REPO / "MapRandomizer")), maps_dir)
    module, data_dir = _extract_bundled_engine()
    return NativeEngine(module, data_dir, maps_dir or data_dir.parent / "maps")


def _extract_bundled_engine() -> tuple[ModuleType, Path]:
    native = _bundled(f"bin/{platform_tag()}/{MODULE_FILE}")
    if native is None:
        raise RuntimeError(f"Super Metroid Map Rando has no engine for {platform_tag()} in this .apworld: build it "
                           f"from the repository (see README).")
    archive = data("engine-data.zip")
    from Utils import cache_path
    target = Path(cache_path("smmr", hashlib.sha256(native + archive).hexdigest()[:16]))
    if not (target / ".complete").exists():
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            zf.extractall(target / "data")
        (target / MODULE_FILE).write_bytes(native)
        (target / ".complete").touch()
    return _load_module(target / MODULE_FILE), target / "data"


def _load_module(path: Path) -> ModuleType:
    loader = importlib.machinery.ExtensionFileLoader("smmr_engine", str(path))
    spec = importlib.util.spec_from_file_location("smmr_engine", path, loader=loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    sys.modules["smmr_engine"] = module
    return module


def ensure_map_pool(map_layout: str) -> None:
    """Download the map layout's pool if this machine doesn't have it yet (hundreds of MB, once)."""
    pool = catalog_info()["map_pools"].get(map_layout)
    if pool is not None:
        from . import fetch
        current = engine()
        fetch.map_pool(current.maps_dir or current.data_dir / "maps", pool)


@lru_cache(maxsize=None)
def catalog_info() -> dict[str, Any]:
    """The engine's `info`, as recorded in data/info.json."""
    return json.loads(data("info.json"))


@lru_cache(maxsize=None)
def catalog() -> Catalog:
    return Catalog.from_info(catalog_info())


@lru_cache(maxsize=None)
def abi() -> Abi:
    return Abi.parse(data("abi.toml").decode())


@lru_cache(maxsize=None)
def full_presets() -> dict[str, Any]:
    """Map Rando's full-settings presets, by name."""
    return json.loads(data("presets.json"))
