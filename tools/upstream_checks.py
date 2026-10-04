"""
Fingerprints of upstream (MapRandomizer) code that this repository mirrors by hand, so that changes upstream get
noticed. If a fingerprint changes, review the corresponding code here and then update the fingerprints:

    python tools/upstream_checks.py           # check (exit code 1 if anything changed)
    python tools/upstream_checks.py --update  # record the current fingerprints
"""
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MR = os.path.join(ROOT, "MapRandomizer")
FINGERPRINTS = os.path.join(ROOT, "tools", "upstream_fingerprints.json")

SCRIPTS = "rust/maprando-web/templates/generate/scripts.html"

# (name, file, regex matching the start of the code, what to review here if it changes)
CHECKS = [
    ("enhanced map preset", SCRIPTS, r"function processEnhancedMapPreset\(",
     "worlds/sm_map_rando/settings_builder.py: _enhanced_map"),
    ("initial map reveal preset", SCRIPTS, r"function processInitialMapRevealPreset\(",
     "worlds/sm_map_rando/settings_builder.py: _initial_map_reveal"),
    ("map station activation preset", SCRIPTS, r"function processMapStationActivationPreset\(",
     "worlds/sm_map_rando/settings_builder.py: _map_station_activation"),
    ("item pool presets", SCRIPTS, r"function \w*[Ii]temPool\w*\(",
     "worlds/sm_map_rando/settings_builder.py: FULL_POOL / REDUCED_POOL"),
    ("Mosaic themes", "rust/maprando-web/src/main.rs", r"let mosaic_themes = vec!\[",
     "native/pysmmaprando/src/lib.rs: mosaic_themes"),
    ("customize settings", "rust/maprando-web/src/seed.rs", r"let customize_settings = CustomizeSettings \{",
     "native/pysmmaprando/src/lib.rs: parse_customize_settings"),
    ("map pools", "rust/maprando-web/src/main.rs", r"let vanilla_map_path",
     "native/pysmmaprando/src/lib.rs: MAP_POOL_VERSION"),
    ("Morph Ball / Pit Room item copies", "rust/maprando/src/patch.rs", r"fn apply_miscellaneous_patches",
     "basepatch / AP item PLMs (item locations copied between room states)"),
]


def _block(text: str, start: int) -> str:
    """The code from `start` to the end of the brace/bracket block that opens on that line."""
    i = start
    while text[i] not in "{[":
        i += 1
    open_char = text[i]
    close_char = "}" if open_char == "{" else "]"
    depth = 0
    for j in range(i, len(text)):
        if text[j] == open_char:
            depth += 1
        elif text[j] == close_char:
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
    return text[start:]


def fingerprints():
    out = {}
    for name, rel, pattern, _ in CHECKS:
        text = open(os.path.join(MR, rel), encoding="utf-8").read()
        matches = list(re.finditer(pattern, text))
        if not matches:
            out[name] = "MISSING"
            continue
        code = "\n".join(_block(text, m.start()) for m in matches)
        code = re.sub(r"\s+", " ", code)
        out[name] = hashlib.sha256(code.encode()).hexdigest()[:16]
    return out


def main():
    current = fingerprints()
    if "--update" in sys.argv:
        json.dump(current, open(FINGERPRINTS, "w"), indent=1)
        print(f"Recorded {len(current)} fingerprints")
        return 0
    recorded = json.load(open(FINGERPRINTS)) if os.path.exists(FINGERPRINTS) else {}
    changed = [c for c in CHECKS if recorded.get(c[0]) != current[c[0]]]
    for name, rel, _, review in changed:
        print(f"CHANGED upstream: {name} ({rel}) -> review {review}")
    if not changed:
        print("Upstream code mirrored by this repository is unchanged.")
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
