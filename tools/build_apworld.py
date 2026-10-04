"""
Assemble the Super Metroid Map Rando world: copy the Map Rando game data, the AP basepatch and the native wheels
into worlds/sm_map_rando, generate the static location/item tables, and zip everything into an .apworld.

Usage: python tools/build_apworld.py [--skip-data] [--no-zip]
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MR = os.path.join(ROOT, "MapRandomizer")
BASEPATCH = os.path.join(ROOT, "SMBasepatch", "build", "romhacks", "maprando")
WORLD = os.path.join(ROOT, "worlds", "sm_map_rando")
DATA = os.path.join(WORLD, "data")
GAME_DATA = os.path.join(DATA, "maprando")
WHEELS = os.path.join(ROOT, "dist", "wheels")

SM_JSON_DATA_FILES = ["tech.json", "items.json", "helpers.json", "numerics.json"]
SM_JSON_DATA_DIRS = ["region", "connection", "enemies", "weapons"]


def copytree(src, dst, pattern=None):
    if pattern is None:
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        os.makedirs(dst, exist_ok=True)
        for f in glob.glob(os.path.join(src, pattern)):
            shutil.copy2(f, dst)


def build_game_data():
    shutil.rmtree(GAME_DATA, ignore_errors=True)
    os.makedirs(GAME_DATA)
    copytree(os.path.join(MR, "rust", "data"), os.path.join(GAME_DATA, "rust", "data"))
    shutil.copy2(os.path.join(MR, "rust", "VERSION"), os.path.join(GAME_DATA, "rust", "VERSION"))
    sm = os.path.join(GAME_DATA, "sm-json-data")
    os.makedirs(sm)
    for f in SM_JSON_DATA_FILES:
        shutil.copy2(os.path.join(MR, "sm-json-data", f), sm)
    for d in SM_JSON_DATA_DIRS:
        shutil.copytree(os.path.join(MR, "sm-json-data", d), os.path.join(sm, d),
                        ignore=shutil.ignore_patterns("*.md", ".*", "*.png", "*.jpg", "*.gif"))
    shutil.copy2(os.path.join(MR, "room_geometry.json"), GAME_DATA)
    copytree(os.path.join(MR, "TitleScreen", "Images"), os.path.join(GAME_DATA, "TitleScreen", "Images"))
    copytree(os.path.join(MR, "gfx", "title"), os.path.join(GAME_DATA, "gfx", "title"))
    copytree(os.path.join(MR, "maps", "vanilla"), os.path.join(GAME_DATA, "maps", "vanilla"))
    copytree(os.path.join(MR, "patches", "ips"), os.path.join(GAME_DATA, "patches", "ips"))
    os.makedirs(os.path.join(GAME_DATA, "patches", "samus_sprites"))
    shutil.copy2(os.path.join(MR, "patches", "samus_sprites", "samus_vanilla.ips"),
                 os.path.join(GAME_DATA, "patches", "samus_sprites"))
    os.makedirs(os.path.join(GAME_DATA, "MapRandoSprites", "samus_sprites"))
    shutil.copy2(os.path.join(MR, "MapRandoSprites", "samus_sprites", "manifest.json"),
                 os.path.join(GAME_DATA, "MapRandoSprites", "samus_sprites"))

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=MR, text=True).strip()
    upstream = subprocess.check_output(["git", "merge-base", "HEAD", "origin/main"], cwd=MR, text=True).strip() \
        if subprocess.call(["git", "rev-parse", "--verify", "-q", "origin/main"], cwd=MR,
                           stdout=subprocess.DEVNULL) == 0 else commit
    with open(os.path.join(DATA, "upstream_commit.txt"), "w") as f:
        f.write(upstream + "\n")
    shutil.copy2(os.path.join(MR, "MOSAIC_BUILD_ID"), os.path.join(DATA, "MOSAIC_BUILD_ID"))


def build_basepatch():
    dst = os.path.join(DATA, "SMBasepatch_prebuilt")
    os.makedirs(dst, exist_ok=True)
    for f in ["multiworld-basepatch.ips", "sm-basepatch-symbols.json"]:
        shutil.copy2(os.path.join(BASEPATCH, f), dst)


def build_tables():
    """Static tables that must be known at import time (location names and ids)."""
    sys.path.insert(0, WORLD)
    import urllib.request
    import pysmmaprando
    mr = pysmmaprando.MapRando(GAME_DATA, os.path.join(ROOT, "dist", "maps-cache"),
                               lambda url, dest: urllib.request.urlretrieve(url, dest))
    locations = json.loads(mr.item_locations())
    # The location id is based on the vanilla item "bit index" (the PLM room argument), which is how the AP
    # basepatch and client identify locations. It isn't available without a ROM, so it comes from a table.
    address_to_bit = json.load(open(os.path.join(ROOT, "tools", "loc_address_to_bit_index.json")))
    out = []
    for loc in locations:
        name = f"{loc['room_name']} {loc['node_name']}"
        out.append({
            "index": loc["index"],
            "name": name,
            "room_id": loc["room_id"],
            "node_id": loc["node_id"],
            "room_name": loc["room_name"],
            "node_name": loc["node_name"],
            "plm_ptr": loc["plm_ptr"],
            "bit_index": address_to_bit[str(loc["plm_ptr"])],
        })
    assert len({x["name"] for x in out}) == len(out)
    assert len({x["bit_index"] for x in out}) == len(out)
    with open(os.path.join(DATA, "locations.json"), "w") as f:
        json.dump(out, f, indent=1)
    start_locations = json.loads(mr.start_locations())
    with open(os.path.join(DATA, "start_locations.json"), "w") as f:
        json.dump(start_locations, f, indent=1)


def copy_wheels():
    lib = os.path.join(WORLD, "lib")
    shutil.rmtree(lib, ignore_errors=True)
    os.makedirs(lib)
    for whl in glob.glob(os.path.join(WHEELS, "pysmmaprando-*.whl")):
        shutil.copy2(whl, lib)


def make_zip():
    out = os.path.join(ROOT, "dist", "sm_map_rando.apworld")
    if os.path.exists(out):
        os.remove(out)
    manifest = json.load(open(os.path.join(WORLD, "archipelago.json")))
    # APContainer packaging version (see worlds/Files.py in Archipelago)
    manifest["version"] = 7
    manifest["compatible_version"] = 7
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("sm_map_rando/archipelago.json", json.dumps(manifest, indent=4))
        for dirpath, dirnames, filenames in os.walk(WORLD):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fn in filenames:
                if fn.endswith(".pyc") or (fn == "archipelago.json" and dirpath == WORLD):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, os.path.dirname(WORLD))
                # files downloaded on demand (when running from the world folder) are not bundled
                parts = rel.replace(os.sep, "/").split("/")
                if "mosaic" in parts or ("samus_sprites" in parts and fn != "samus_vanilla.ips"
                                         and not fn.endswith(".json")):
                    continue
                # wheels and other already-compressed files are stored as-is
                compress = zipfile.ZIP_STORED if fn.endswith((".whl", ".png")) else zipfile.ZIP_DEFLATED
                zf.write(full, rel.replace(os.sep, "/"), compress_type=compress)
    print(f"Wrote {out} ({os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-data", action="store_true")
    parser.add_argument("--no-zip", action="store_true")
    args = parser.parse_args()
    if not args.skip_data:
        build_game_data()
    build_basepatch()
    build_tables()
    copy_wheels()
    if not args.no_zip:
        make_zip()
