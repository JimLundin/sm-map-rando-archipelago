"""
Assemble the Archipelago multiworld basepatch for Map Rando (basepatch/romhacks/maprando) into
worlds/sm_map_rando/data/SMBasepatch_prebuilt, and check that it doesn't overlap Map Rando's own patches.

The assembler (asar) is built from the MapRandomizer submodule's asar sources if it isn't found (requires CMake and a
C++ compiler), or can be given with the ASAR environment variable.

Usage: python tools/build_basepatch.py
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ips_ranges import ips_ranges, merge, pc2snes  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASEPATCH = os.path.join(ROOT, "basepatch")
OUT = os.path.join(ROOT, "worlds", "sm_map_rando", "data", "SMBasepatch_prebuilt")
ASAR_BIN = os.path.join(ROOT, "tools", "bin", "asar.exe" if os.name == "nt" else "asar")

# Byte ranges deliberately shared with Map Rando's patches: the copy protection byte (same value), and the hook in
# Map Rando's LoadGame (saveload.asm).
ALLOWED_OVERLAPS = {("sram_check_disable.ips", 0x808000), ("saveload.ips", 0x81F0BF)}


def find_asar() -> str:
    if os.getenv("ASAR"):
        return os.environ["ASAR"]
    if os.path.exists(ASAR_BIN):
        return ASAR_BIN
    print("Building asar from MapRandomizer/asar")
    src = os.path.join(ROOT, "MapRandomizer", "asar", "src")
    build = tempfile.mkdtemp(prefix="asar-build-")
    subprocess.check_call(["cmake", src, "-DCMAKE_BUILD_TYPE=Release"], cwd=build, stdout=subprocess.DEVNULL)
    subprocess.check_call(["cmake", "--build", ".", "--config", "Release", "--parallel"], cwd=build,
                          stdout=subprocess.DEVNULL)
    exe = "asar.exe" if os.name == "nt" else "asar"
    built = [p for p in glob.glob(os.path.join(build, "asar", "bin", "**", exe), recursive=True) if os.path.isfile(p)]
    if not built:
        raise SystemExit("asar build failed")
    os.makedirs(os.path.dirname(ASAR_BIN), exist_ok=True)
    shutil.copy2(built[0], ASAR_BIN)
    return ASAR_BIN


def main():
    asar = find_asar()
    os.makedirs(OUT, exist_ok=True)
    resources = os.path.join(BASEPATCH, "resources")
    src_dir = os.path.join(BASEPATCH, "romhacks", "maprando")
    with tempfile.TemporaryDirectory() as tmp:
        roms = [os.path.join(tmp, "00.sfc"), os.path.join(tmp, "ff.sfc")]
        sym = os.path.join(OUT, "multiworld.sym")
        subprocess.check_call([sys.executable, os.path.join(resources, "create_dummies.py"), *roms])
        for rom in roms:
            result = subprocess.run([asar, "--no-title-check", "--symbols=wla", f"--symbols-path={sym}", "main.asm",
                                     rom], cwd=src_dir, capture_output=True, text=True)
            if result.returncode != 0 or not os.path.exists(sym):
                raise SystemExit(f"Assembling the basepatch failed:\n{result.stdout}\n{result.stderr}")
        subprocess.check_call([sys.executable, os.path.join(resources, "create_ips.py"), *roms,
                               os.path.join(OUT, "multiworld-basepatch.ips")])
    with open(os.path.join(OUT, "sm-basepatch-symbols.json"), "w") as f:
        subprocess.check_call([sys.executable, os.path.join(resources, "sym2json.py"), sym,
                               *sorted(glob.glob(os.path.join(BASEPATCH, "common", "*.asm")))], stdout=f)
    os.remove(sym)

    # The basepatch must not overwrite anything from Map Rando's patches
    base = merge(ips_ranges(os.path.join(OUT, "multiworld-basepatch.ips")))
    problems = []
    for path in sorted(glob.glob(os.path.join(ROOT, "MapRandomizer", "patches", "ips", "**", "*.ips"),
                                 recursive=True)):
        name = os.path.basename(path)
        for s, e in ips_ranges(path):
            for bs, be in base:
                if s < be and bs < e and (name, pc2snes(max(s, bs))) not in ALLOWED_OVERLAPS:
                    problems.append(f"{name}: {pc2snes(max(s, bs)):06X}-{pc2snes(min(e, be) - 1):06X}")
    if problems:
        raise SystemExit("The basepatch overlaps Map Rando's patches:\n  " + "\n  ".join(problems))
    print(f"Built {OUT}/multiworld-basepatch.ips (no overlap with Map Rando's patches)")


if __name__ == "__main__":
    main()
