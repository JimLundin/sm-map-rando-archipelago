"""Run one pipeline stage from artifact files, for a short edit → run loop.

    uv run tools/stage.py upgrade fixtures/settings/default-vanilla.json -o build/settings.json
    uv run tools/stage.py randomize build/settings.json --seed 1 -o build/seed.json
    uv run tools/stage.py rom build/settings.json build/seed.json --rom vanilla.sfc -o build/mr.sfc
    uv run tools/stage.py info -o build/info.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "world" / "smmr"))   # `core` alone: importing `smmr` needs Archipelago

from core.engine import NativeEngine  # noqa: E402
from local_engine import local_engine  # noqa: E402


def default_engine() -> NativeEngine:
    return local_engine()


def load(path: str):
    return json.loads(Path(path).read_text())


def save(obj: object, path: str) -> None:
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
