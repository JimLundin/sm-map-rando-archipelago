"""Where the engine and its data are on this machine.

- Development (the world runs from the repository, e.g. symlinked into Archipelago): `SMMR_ENGINE` (the binary) and
  `SMMR_DATA` (a MapRandomizer checkout with `tools/fetch_data.py` run), defaulting to the repository's builds.
- Release: the .apworld bundles the engine for each platform (`bin/<platform>/`) and Map Rando's data
  (`data/engine-data.zip`, see tools/build_apworld.py). They are extracted to Archipelago's cache on first use, into
  a directory named by their hash, so a new release never runs with an old copy.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import pkgutil
import sys
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from .core.abi import Abi
from .core.catalog import Catalog
from .core.engine import SubprocessEngine, platform_tag

REPO = Path(__file__).resolve().parents[2]


def data(name: str) -> bytes:
    """A file in the world's data/ (works from a zipped .apworld too)."""
    content = pkgutil.get_data(__package__, f"data/{name}")
    assert content is not None
    return content


def _bundled(name: str) -> Optional[bytes]:
    try:
        return pkgutil.get_data(__package__, name)
    except OSError:
        return None


@lru_cache(maxsize=None)
def engine() -> SubprocessEngine:
    maps = os.environ.get("SMMR_MAPS")
    maps_dir = Path(maps) if maps else None
    if "SMMR_ENGINE" in os.environ or (REPO / "engine").is_dir():
        binary = Path(os.environ.get("SMMR_ENGINE", REPO / "engine/target/dev-release/smmr-engine"))
        data_dir = Path(os.environ.get("SMMR_DATA", REPO / "MapRandomizer"))
        return SubprocessEngine(binary, data_dir, maps_dir)
    return _extract_bundled_engine(maps_dir)


def _extract_bundled_engine(maps_dir: Optional[Path]) -> SubprocessEngine:
    executable = "smmr-engine.exe" if sys.platform == "win32" else "smmr-engine"
    binary = _bundled(f"bin/{platform_tag()}/{executable}")
    if binary is None:
        raise RuntimeError(f"Super Metroid Map Rando has no engine for {platform_tag()} in this .apworld: build it "
                           f"from the repository (see README), then set SMMR_ENGINE and SMMR_DATA.")
    archive = data("engine-data.zip")
    from Utils import cache_path
    target = Path(cache_path("smmr", hashlib.sha256(binary + archive).hexdigest()[:16]))
    if not (target / ".complete").exists():
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            zf.extractall(target / "data")
        (target / executable).write_bytes(binary)
        (target / executable).chmod(0o755)
        (target / ".complete").touch()
    return SubprocessEngine(target / executable, target / "data", maps_dir or target / "maps")


@lru_cache(maxsize=None)
def catalog() -> Catalog:
    return Catalog.from_info(json.loads(data("info.json")))


@lru_cache(maxsize=None)
def abi() -> Abi:
    return Abi.parse(data("abi.toml").decode())


def preset(name: str) -> Dict[str, Any]:
    return json.loads(data("presets.json"))[name]
