"""Bundle Map Rando's full-settings presets as world data (`world/smmr/data/presets.json`)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRESETS = ROOT / "MapRandomizer" / "rust" / "data" / "presets" / "full-settings"

presets = {path.stem: json.loads(path.read_text()) for path in sorted(PRESETS.glob("*.json"))}
(ROOT / "world" / "smmr" / "data" / "presets.json").write_text(json.dumps(presets, indent=1))
