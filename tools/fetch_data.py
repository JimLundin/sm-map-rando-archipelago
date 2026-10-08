"""Download the Map Rando data that isn't in its repository into the MapRandomizer checkout, where the engine looks.

    python tools/fetch_data.py            # Mosaic tile patches (needed to build any ROM)
    python tools/fetch_data.py --maps     # also the Small/Standard/Wild map pools (~1 GB)

The world downloads map pools itself when a seed needs one; this is for development and building the .apworld.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "world" / "smmr"))

import fetch  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "MapRandomizer")
    parser.add_argument("--maps", action="store_true", help="also download the map pools")
    args = parser.parse_args()
    print(fetch.mosaic(args.data))
    if args.maps:
        pools = json.loads((ROOT / "world/smmr/data/info.json").read_text())["map_pools"]
        for pool in pools.values():
            print(fetch.map_pool(args.data / "maps", pool))


if __name__ == "__main__":
    main()
