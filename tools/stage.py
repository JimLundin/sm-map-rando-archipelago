"""Run one pipeline stage from artifact files, for a short edit → run loop.

    python tools/stage.py upgrade fixtures/settings/default-vanilla.json -o build/settings.json
    python tools/stage.py randomize build/settings.json --seed 1 -o build/seed.json
    python tools/stage.py rom build/settings.json build/seed.json --rom vanilla.sfc -o build/mr.sfc
    python tools/stage.py info -o build/info.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "world"))

from smmr.core.engine import SubprocessEngine  # noqa: E402


def default_engine() -> SubprocessEngine:
    binary = Path(os.environ.get("SMMR_ENGINE", ROOT / "engine/target/dev-release/smmr-engine"))
    data = Path(os.environ.get("SMMR_DATA", ROOT / "MapRandomizer"))
    maps = os.environ.get("SMMR_MAPS")
    return SubprocessEngine(binary, data, Path(maps) if maps else None)


def load(path: str):
    return json.loads(Path(path).read_text())


def save(obj, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="stage", required=True)
    p = sub.add_parser("info")
    p.add_argument("-o", required=True)
    p = sub.add_parser("upgrade")
    p.add_argument("settings")
    p.add_argument("-o", required=True)
    p = sub.add_parser("randomize")
    p.add_argument("settings")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("-o", required=True)
    p = sub.add_parser("rom")
    p.add_argument("settings")
    p.add_argument("seed")
    p.add_argument("--rom", required=True)
    p.add_argument("-o", required=True)
    args = parser.parse_args()

    engine = default_engine()
    if args.stage == "info":
        save(engine.info(), args.o)
    elif args.stage == "upgrade":
        save(engine.upgrade(load(args.settings)), args.o)
    elif args.stage == "randomize":
        save(engine.randomize(load(args.settings), args.seed), args.o)
    elif args.stage == "rom":
        engine.rom(load(args.settings), load(args.seed)["randomization"], Path(args.rom), Path(args.o))


if __name__ == "__main__":
    main()
