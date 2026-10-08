"""Download the Map Rando data that isn't in its repository, the way upstream's `scripts/download_data.sh` does.

    python tools/fetch_data.py            # Mosaic tile patches (needed to build any ROM)
    python tools/fetch_data.py --maps     # also the Small/Standard/Wild map pools (~1 GB)

Both go into the MapRandomizer checkout (`patches/mosaic`, `maps/<pool>`), where the engine looks for them.
"""
from __future__ import annotations

import argparse
import io
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = "https://map-rando-artifacts.s3.us-west-004.backblazeb2.com"
MAP_POOLS = ["v119-small-avro", "v119-standard-avro", "v119-wild-avro"]


def zstd_decompress(data: bytes) -> bytes:
    try:
        from compression import zstd  # Python 3.14+
    except ImportError:
        from backports import zstd  # type: ignore[no-redef]
    return zstd.decompress(data)


def download(url: str, scratch: Path) -> Path:
    target = scratch / url.rsplit("/", 1)[1]
    print(f"downloading {url}")
    with urllib.request.urlopen(url) as response, open(target, "wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
    return target


def extract(tar_bytes: bytes, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        tar.extractall(dest, filter="data")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "MapRandomizer")
    parser.add_argument("--maps", action="store_true", help="also download the map pools")
    args = parser.parse_args()
    data: Path = args.data

    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        mosaic = data / "patches" / "mosaic"
        if not (mosaic / "tilesets.bps").exists():
            build_id = (data / "MOSAIC_BUILD_ID").read_text().strip()
            archive = download(f"{ARTIFACTS}/Mosaic/Mosaic-{build_id}.tar.zstd", scratch)
            extract(zstd_decompress(archive.read_bytes()), mosaic)
        if args.maps:
            for pool in MAP_POOLS:
                if not (data / "maps" / pool).is_dir():
                    archive = download(f"{ARTIFACTS}/maps/{pool}.tar", scratch)
                    extract(archive.read_bytes(), data / "maps")
                    archive.unlink()


if __name__ == "__main__":
    main()
