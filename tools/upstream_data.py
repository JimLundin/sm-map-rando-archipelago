"""
Map Rando data used to generate the Archipelago world, read from the MapRandomizer submodule:
- the settings structure and enum values (settings.rs, see rust_schema.py),
- the map layouts (map_repository.rs),
- the presets, exactly as loaded by Map Rando itself (through the native module),
- the website's labels and help texts (tools/settings_catalog.json, extracted from the website templates by
  tools/catalog/build_catalog.py). These are documentation only: the options can be generated without them.
"""
import functools
import json
import os
import re
import urllib.request

import rust_schema

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MR = os.path.join(ROOT, "MapRandomizer")
GAME_DATA = os.path.join(ROOT, "worlds", "sm_map_rando", "data", "maprando")
CATALOG = os.path.join(ROOT, "tools", "settings_catalog.json")


@functools.lru_cache(maxsize=None)
def schema():
    """{path: (kind, detail)} for every leaf of Map Rando's settings JSON."""
    structs, enums = rust_schema.parse()
    return {path: (kind, detail) for path, kind, detail in rust_schema.leaf_settings(structs, enums)}


@functools.lru_cache(maxsize=None)
def map_layouts():
    src = open(os.path.join(MR, "rust", "maprando", "src", "map_repository.rs"), encoding="utf-8").read()
    body = src[src.index("fn from_map_layout"):]
    body = body[:body.index("_ =>")]
    layouts = re.findall(r'"(\w+)"\s*=>', body)
    if not layouts:
        raise RuntimeError("Could not find the map layouts in map_repository.rs")
    return layouts


@functools.lru_cache(maxsize=None)
def presets():
    """The presets as loaded by Map Rando: {"full": [...], "skill": [...], ...} (JSON values), in website order."""
    import pysmmaprando
    mr = pysmmaprando.MapRando(GAME_DATA, os.path.join(ROOT, "dist", "maps-cache"),
                               lambda url, dest: urllib.request.urlretrieve(url, dest))
    return json.loads(mr.presets_json())


def preset_names(category: str):
    key = "name" if category == "full" else "preset"
    return [p[key] for p in presets()[category]]


@functools.lru_cache(maxsize=None)
def catalog():
    if not os.path.exists(CATALOG):
        return {"randomizer_settings": [], "customize_settings": []}
    return json.load(open(CATALOG, encoding="utf-8"))


def catalog_entry(path: str, kind: str = "randomizer_settings"):
    for e in catalog()[kind]:
        if e["path"] == path:
            return e
    return None
