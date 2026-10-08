"""End to end, from the packaged world: generate with dist/smmr.apworld in an Archipelago checkout, patch the
player's ROM the way the client does, and boot it to gameplay in the emulator.

    python tools/e2e.py --ap /path/to/clean/Archipelago --rom vanilla.sfc

The Archipelago checkout must not have worlds/smmr (the development symlink): the .apworld is copied to its
custom_worlds/.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PATCH_AND_BOOT = """
import sys, zipfile
sys.argv = sys.argv[:1]
import worlds  # loads custom_worlds/smmr.apworld
from worlds.smmr.patch import SMMRProcedurePatch, vanilla_rom_bytes
patch_file, rom, out, tools = {patch!r}, {rom!r}, {out!r}, {tools!r}
SMMRProcedurePatch.source_data = vanilla_rom_bytes(rom)
SMMRProcedurePatch(patch_file).patch(out)
sys.path.insert(0, tools)
from emu import Emulator
emu = Emulator(open(out, "rb").read())
for i in range(300):
    emu.run(10)
    if i % 6 == 0:
        emu.press("start")
    if emu.wram.u16(0x998) == 8:
        print("E2E-OK gameplay at frame", emu.frame)
        break
else:
    sys.exit("the ROM didn't reach gameplay")
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ap", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--apworld", type=Path, default=ROOT / "dist" / "smmr.apworld")
    args = parser.parse_args()
    if (args.ap / "worlds" / "smmr").exists():
        sys.exit(f"{args.ap}/worlds/smmr exists: use an Archipelago checkout without the development symlink")
    (args.ap / "custom_worlds").mkdir(exist_ok=True)
    shutil.copy(args.apworld, args.ap / "custom_worlds" / "smmr.apworld")

    env = {"SKIP_REQUIREMENTS_UPDATE": "1", "PATH": "/usr/bin:/bin"}
    with tempfile.TemporaryDirectory() as tmp:
        players, out = Path(tmp) / "players", Path(tmp) / "out"
        players.mkdir()
        (players / "p1.yaml").write_text("name: Samus\ngame: Super Metroid Map Rando\n"
                                         "Super Metroid Map Rando:\n  map_layout: vanilla\n")
        subprocess.run([sys.executable, "Generate.py", "--player_files_path", str(players), "--outputpath", str(out)],
                       cwd=args.ap, env=env, check=True)
        archive = next(out.glob("AP_*.zip"))
        with zipfile.ZipFile(archive) as zf:
            name = next(n for n in zf.namelist() if n.endswith(".apsmmr"))
            zf.extract(name, out)
        script = PATCH_AND_BOOT.format(patch=str(out / name), rom=str(args.rom.resolve()), out=str(out / "seed.sfc"),
                                       tools=str(ROOT / "tools"))
        result = subprocess.run([sys.executable, "-c", script], cwd=args.ap, env=env, capture_output=True, text=True)
        print(result.stdout[-2000:], result.stderr[-2000:] if result.returncode else "")
        if result.returncode or "E2E-OK" not in result.stdout:
            sys.exit("end to end failed")


if __name__ == "__main__":
    main()
