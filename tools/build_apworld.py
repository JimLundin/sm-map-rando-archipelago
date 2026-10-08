"""Build dist/smmr.apworld: the world package, the engine binaries and Map Rando's data.

    python tools/build_apworld.py                       # this platform's engine (engine/target/release)
    python tools/build_apworld.py --engine linux-x86_64=path/to/smmr-engine --engine win32-amd64=...  # CI

Map Rando's data is the part of the MapRandomizer checkout the engine reads (`tools/fetch_data.py` first, for the
Mosaic patches): it goes into `data/engine-data.zip`, which the world extracts to Archipelago's cache.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORLD = ROOT / "world" / "smmr"
sys.path.insert(0, str(WORLD))

# What the engine reads, relative to the MapRandomizer checkout (found by tracing it). Map pools other than the
# vanilla map are downloaded by the world when a seed needs them.
ENGINE_DATA = ["rust/data", "sm-json-data", "patches/ips", "patches/mosaic", "patches/samus_sprites/samus_vanilla.ips",
               "TitleScreen", "gfx", "maps/vanilla", "room_geometry.json", "transit-tube-data"]
SKIP_SUFFIXES = (".png", ".md", ".txt", ".pyc")
KEEP_PNG = ("TitleScreen", "gfx", "rust/data")   # images the engine does read


def engine_data_zip(data_root: Path) -> bytes:
    import io
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for entry in ENGINE_DATA:
            path = data_root / entry
            if not path.exists():
                sys.exit(f"missing {path} (run tools/fetch_data.py?)")
            files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
            for file in files:
                relative = file.relative_to(data_root).as_posix()
                if ".git" in file.parts:
                    continue
                if file.suffix in SKIP_SUFFIXES and not (file.suffix == ".png" and relative.startswith(KEEP_PNG)):
                    continue
                zf.write(file, relative)
    return buffer.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", action="append", default=[], metavar="PLATFORM=PATH")
    parser.add_argument("--data", type=Path, default=ROOT / "MapRandomizer")
    parser.add_argument("-o", type=Path, default=ROOT / "dist" / "smmr.apworld")
    args = parser.parse_args()

    from core.engine import platform_tag
    engines = dict(spec.split("=", 1) for spec in args.engine) or {
        platform_tag(): str(ROOT / "engine" / "target" / "release" /
                            ("smmr-engine.exe" if sys.platform == "win32" else "smmr-engine"))}
    args.o.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.o, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(WORLD.rglob("*")):
            relative = file.relative_to(WORLD)
            if (file.is_dir() or "__pycache__" in relative.parts or relative.parts[0] == "test"
                    or relative.name == "archipelago.json"):
                continue
            zf.write(file, f"smmr/{relative.as_posix()}")
        # Archipelago's container format (worlds/Files.py APContainer): version 7, readable by patch system 5+.
        manifest = {**json.loads((WORLD / "archipelago.json").read_text()), "version": 7, "compatible_version": 5}
        zf.writestr("smmr/archipelago.json", json.dumps(manifest, indent=4))
        zf.writestr("smmr/data/engine-data.zip", engine_data_zip(args.data), zipfile.ZIP_STORED)
        for tag, path in engines.items():
            name = "smmr-engine.exe" if tag.startswith("win32") else "smmr-engine"
            zf.write(path, f"smmr/bin/{tag}/{name}")
    print(f"{args.o}: {args.o.stat().st_size / 1e6:.1f} MB, engines for {', '.join(engines)}")


if __name__ == "__main__":
    main()
