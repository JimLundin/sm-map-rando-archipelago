"""Bundle Map Rando's full-settings presets as world data (`world/smmr/data/presets.json`). The category presets need
no copy: the engine's `info` lists their names, and Map Rando's upgrade expands a category preset from its name."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRESETS = ROOT / "MapRandomizer" / "rust" / "data" / "presets" / "full-settings"

presets = {path.stem: json.loads(path.read_text()) for path in sorted(PRESETS.glob("*.json"))}
(ROOT / "world" / "smmr" / "data" / "presets.json").write_text(json.dumps(presets, indent=1))
