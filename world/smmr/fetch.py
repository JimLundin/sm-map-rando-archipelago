"""Downloads of Map Rando data that isn't in its repository: the map pools (Small/Standard/Wild) and the Mosaic tile
patches, from the artifacts host Map Rando's own scripts/download_data.sh uses. Standard library only, so that
tools/fetch_data.py can use it outside Archipelago.

Downloads are untrusted data: each goes into its own new temporary directory, and archives are extracted with
tarfile's "data" filter (no links out of the target, no special files).
"""
from __future__ import annotations

import io
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ARTIFACTS = "https://map-rando-artifacts.s3.us-west-004.backblazeb2.com"


def _download(url: str, scratch: Path) -> Path:
    target = scratch / url.rsplit("/", 1)[1]
    with urllib.request.urlopen(url) as response, open(target, "wb") as out:
        shutil.copyfileobj(response, out, 1 << 20)
    return target


def _extract(tar: "Path | bytes", dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    source = tarfile.open(fileobj=io.BytesIO(tar)) if isinstance(tar, bytes) else tarfile.open(tar)
    with source as archive:
        archive.extractall(dest, filter="data")


def map_pool(maps_dir: Path, pool: str) -> Path:
    """`maps_dir/pool`, downloaded first if it isn't there yet."""
    target = maps_dir / pool
    if not target.is_dir():
        with tempfile.TemporaryDirectory() as tmp:
            unpacked = Path(tmp) / "unpacked"
            _extract(_download(f"{ARTIFACTS}/maps/{pool}.tar", Path(tmp)), unpacked)
            maps_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(unpacked / pool), str(target))   # whole, so a failed download leaves nothing
    return target


def mosaic(data_dir: Path) -> Path:
    """`data_dir/patches/mosaic` for the Mosaic build in `data_dir/MOSAIC_BUILD_ID`, downloaded if missing."""
    target = data_dir / "patches" / "mosaic"
    if not (target / "tilesets.bps").exists():
        build_id = (data_dir / "MOSAIC_BUILD_ID").read_text().strip()
        try:
            from compression import zstd  # pyright: ignore[reportMissingImports]  (Python 3.14+)
        except ImportError:
            from backports import zstd  # type: ignore[no-redef]
        with tempfile.TemporaryDirectory() as tmp:
            archive = _download(f"{ARTIFACTS}/Mosaic/Mosaic-{build_id}.tar.zstd", Path(tmp))
            _extract(zstd.decompress(archive.read_bytes()), target)
    return target
