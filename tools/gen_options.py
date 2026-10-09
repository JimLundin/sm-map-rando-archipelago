"""
Generate worlds/sm_map_rando_upstream/Options.py (and data/presets_index.json) for the Map Rando settings.

The settings themselves come from Map Rando: the structure and enum values from settings.rs, the presets as loaded by
Map Rando (see upstream_data.py). The specification below only adds what Map Rando doesn't define: stable option
names, numeric ranges and grouping. Labels and help texts come from the website templates (settings_catalog.json),
where available. Settings added upstream that aren't in the specification get options automatically (with a
warning, so that they can be given a proper name and range).

Usage: python tools/gen_options.py
"""
import json
import os
import re
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rust_schema  # noqa: E402
import upstream_data  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = upstream_data.catalog()
GAME_DATA = os.path.join(ROOT, "worlds", "sm_map_rando_upstream", "data", "maprando")
OUT = os.path.join(ROOT, "worlds", "sm_map_rando_upstream", "Options.py")
PRESETS_INDEX = os.path.join(ROOT, "worlds", "sm_map_rando_upstream", "data", "presets_index.json")
SCHEMA = upstream_data.schema()
_, RUST_ENUMS = rust_schema.parse()
WARNINGS = []


class CatalogEntries(dict):
    """Website labels/help texts by setting path, with a fallback for settings missing from the catalog."""

    def __missing__(self, path):
        label = path.split(".")[-1].replace("_", " ").capitalize()
        WARNINGS.append(f"no website label/help text for {path}")
        return {"path": path, "label": label, "description": "", "choices": None}


RS = CatalogEntries({e["path"]: e for e in CATALOG["randomizer_settings"]})
CS = {e["path"]: e for e in CATALOG["customize_settings"]}

# Settings that are set by the world itself rather than by options
NOT_OPTIONS = {"version", "name", "debug", "other_settings.random_seed", "start_location_settings.room_id",
               "start_location_settings.node_id"}
PRESET_CATEGORIES = {"skill-assumptions": "skill", "item-progression": "item_progression",
                     "quality-of-life": "quality_of_life", "objectives": "objectives", "doors": "doors"}
LIST_ENUMS = {"objective_settings.objective_options": "ObjectiveSetting",
              "item_progression_settings.key_item_priority": "KeyItemPriority",
              "item_progression_settings.filler_items": "FillerItemPriority"}


def class_name(option_name):
    return "".join(part.capitalize() for part in option_name.split("_"))


def key_for(value):
    """Option key (Python identifier suffix) for a JSON value."""
    s = str(value)
    s = s.replace("+", " plus").replace("3-Tiered", "three tiered").replace("4-Tiered", "four tiered")
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)  # CamelCase -> words
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    if not s or s[0].isdigit():
        s = "x" + s
    if s == "random":
        s = "randomized"  # "random" is reserved by Archipelago (random choice)
    return s


def clean(text):
    text = (text or "").replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def docstring(label, description, extra=""):
    lines = [label.rstrip(".") + "." if label else ""]
    desc = clean(description)
    if desc:
        lines.append("")
        lines.extend(desc.split("\n"))
    if extra:
        lines.append("")
        lines.extend(extra.split("\n"))
    out = []
    for line in lines:
        if not line.strip():
            out.append("")
            continue
        indent = "  " if line.lstrip().startswith("-") else ""
        out.extend(textwrap.wrap(line, 110, subsequent_indent=indent + ("  " if indent else "")) or [""])
    body = "\n".join("    " + l if l else "" for l in out).replace('"""', "'''").replace("\\", "\\\\")
    return f'    """\n{body}\n    """\n'


PRESET_NOTE = "'preset' keeps the value from the selected preset."

# ---------------------------------------------------------------------------------------------------------------------
# Specification of the options: (option name, setting path, kind, extras)
#   kinds: "choice" (enum), "toggle", "int", "float": individual settings, defaulting to the preset's value
#          "category": a category preset (named preset of a whole settings category)
#          "sub_preset": a preset of a group of settings within a category
# ---------------------------------------------------------------------------------------------------------------------

SKILL = "skill_assumption_settings."
ITEMS = "item_progression_settings."
QOL = "quality_of_life_settings."
EMAP = QOL + "enhanced_map_settings."
REVEAL = QOL + "initial_map_reveal_settings."
MSA = QOL + "map_station_activation_settings."
CRASH = QOL + "crash_fixes."
OTHER = "other_settings."
AREA = OTHER + "area_assignment."

SPEC = []


def add(group, name, path, kind, **extra):
    SPEC.append(dict(group=group, name=name, path=path, kind=kind, **extra))


G = "Map Rando Presets"
add(G, "skill_assumptions_preset", SKILL + "preset", "category",
    values=["Basic", "Medium", "Hard", "Very Hard", "Expert", "Expert+", "Extreme", "Extreme+", "Insane", "Insane+",
            "Implicit", "Beyond"], preset_dir="skill-assumptions")
add(G, "item_progression_preset", ITEMS + "preset", "category",
    values=["Normal", "Tricky", "Technical", "Challenge", "Desolate"], preset_dir="item-progression")
add(G, "quality_of_life_preset", QOL + "preset", "category",
    values=["Off", "Low", "Default", "High", "Max"], preset_dir="quality-of-life")
add(G, "objectives_preset", "objective_settings.preset", "category",
    values=["None", "Bosses", "Minibosses", "Chozos", "Pirates", "Metroids", "Random"], preset_dir="objectives")
add(G, "doors_preset", "doors_settings.preset", "category", values=["Blue", "Ammo", "Beam"], preset_dir="doors")

G = "Skill Assumptions"
for name, field, kind, lo, hi in [
    ("shinespark_tiles", "shinespark_tiles", "float", 0, 100),
    ("heated_shinespark_tiles", "heated_shinespark_tiles", "float", 0, 100),
    ("speed_ball_tiles", "speed_ball_tiles", "float", 0, 100),
    ("shinecharge_leniency_frames", "shinecharge_leniency_frames", "int", 0, 600),
    ("resource_multiplier", "resource_multiplier", "float", 1, 10),
    ("farm_time_limit", "farm_time_limit", "float", 30, 600),
    ("gate_glitch_leniency", "gate_glitch_leniency", "int", 0, 100),
    ("door_stuck_leniency", "door_stuck_leniency", "int", 0, 100),
    ("bomb_into_cf_leniency", "bomb_into_cf_leniency", "int", 0, 100),
    ("jump_into_cf_leniency", "jump_into_cf_leniency", "int", 0, 100),
    ("flash_suit_distance", "flash_suit_distance", "int", 0, 255),
    ("blue_suit_distance", "blue_suit_distance", "int", 0, 255),
    ("spike_suit_leniency", "spike_suit_leniency", "int", 0, 100),
    ("spike_xmode_leniency", "spike_xmode_leniency", "int", 0, 100),
    ("spike_speed_keep_leniency", "spike_speed_keep_leniency", "int", 0, 100),
    ("elevator_cf_leniency", "elevator_cf_leniency", "int", 0, 100),
    ("crystal_spark_leniency", "crystal_spark_leniency", "int", 0, 100),
    ("phantoon_proficiency", "phantoon_proficiency", "float", 0, 1),
    ("draygon_proficiency", "draygon_proficiency", "float", 0, 1),
    ("ridley_proficiency", "ridley_proficiency", "float", 0, 1),
    ("botwoon_proficiency", "botwoon_proficiency", "float", 0, 1),
    ("mother_brain_proficiency", "mother_brain_proficiency", "float", 0, 1),
    ("escape_timer_multiplier", "escape_timer_multiplier", "float", 0, 10),
]:
    add(G, name, SKILL + field, kind, min=lo, max=hi,
        integer_valued=field in ("shinespark_tiles", "heated_shinespark_tiles", "speed_ball_tiles", "farm_time_limit"))
add(G, "tech_enabled", SKILL + "tech_settings", "tech")
add(G, "tech_disabled", SKILL + "tech_settings", "tech")
add(G, "notables_enabled", SKILL + "notable_settings", "notables")
add(G, "notables_disabled", SKILL + "notable_settings", "notables")

G = "Item Progression"
add(G, "progression_rate", ITEMS + "progression_rate", "choice")
add(G, "item_placement_style", ITEMS + "item_placement_style", "choice")
add(G, "item_priority_strength", ITEMS + "item_priority_strength", "choice")
add(G, "random_tank", ITEMS + "random_tank", "toggle")
add(G, "spazer_before_plasma", ITEMS + "spazer_before_plasma", "toggle")
add(G, "ammo_collect_fraction", ITEMS + "ammo_collect_fraction", "float", min=0, max=1)
add(G, "item_pool_preset", ITEMS + "item_pool_preset", "sub_preset", values=["Full", "Reduced"])
add(G, "stop_item_placement_early", ITEMS + "stop_item_placement_early", "toggle")
add(G, "item_pool", ITEMS + "item_pool", "item_pool")
add(G, "missile_size", ITEMS + "missile_size", "int", min=1, max=999)
add(G, "super_size", ITEMS + "super_size", "int", min=1, max=99)
add(G, "powerbomb_size", ITEMS + "powerbomb_size", "int", min=1, max=99)
add(G, "etank_size", ITEMS + "etank_size", "int", min=1, max=14)
add(G, "reserve_size", ITEMS + "reserve_size", "int", min=1, max=4)
add(G, "starting_items_preset", ITEMS + "starting_items_preset", "sub_preset", values=["None", "All"])
add(G, "rando_starting_items", ITEMS + "starting_items", "starting_items")
add(G, "key_item_priority", ITEMS + "key_item_priority", "key_item_priority")
add(G, "filler_items", ITEMS + "filler_items", "filler_items")

G = "Quality of Life: Map"
add(G, "enhanced_map", EMAP + "preset", "sub_preset", values=["No", "Yes"])
for f in ["blue_doors", "gray_doors", "ammo_doors", "beam_doors", "heat", "water", "lava", "acid", "walls",
          "objectives", "map_station", "refill_station"]:
    add(G, "enhanced_map_" + f, EMAP + f, "choice")
add(G, "initial_map_reveal", REVEAL + "preset", "sub_preset", values=["No", "Maps", "Partial", "Full", "Global"])
for f in ["map_stations", "save_stations", "refill_stations", "ship", "objectives", "area_transitions", "items1",
          "items2", "items3", "items4", "other"]:
    add(G, "initial_map_reveal_" + f, REVEAL + f, "choice")
add(G, "initial_map_reveal_all_areas", REVEAL + "all_areas", "toggle")
add(G, "map_station_activation", MSA + "preset", "sub_preset", values=["Partial", "Full"])
for f in ["save_stations", "refill_stations", "ship", "objectives", "area_transitions", "items1", "items2", "items3",
          "items4", "other", "sub_area"]:
    add(G, "map_station_activation_" + f, MSA + f, "choice")
add(G, "item_markers", QOL + "item_markers", "choice")
add(G, "room_outline_revealed", QOL + "room_outline_revealed", "toggle")
add(G, "opposite_area_revealed", QOL + "opposite_area_revealed", "toggle")
add(G, "hazard_markers", QOL + "hazard_markers", "toggle")

G = "Quality of Life: Gameplay"
for f in ["mother_brain_fight"]:
    add(G, f, QOL + f, "choice")
for f in ["supers_double", "escape_autosave", "escape_movement_items", "escape_refill", "escape_enemies_cleared",
          "fast_elevators", "fast_doors", "fast_pause_menu", "fast_saves", "fast_baby_cutscene",
          "fast_mother_brain_cutscene", "fast_decompression"]:
    add(G, f, QOL + f, "toggle")
add(G, "fanfares", QOL + "fanfares", "choice")
for f in ["respin", "infinite_space_jump", "momentum_conservation", "all_items_spawn", "acid_chozo",
          "remove_climb_lava"]:
    add(G, f, QOL + f, "toggle")
add(G, "crash_fixes", CRASH + "preset", "sub_preset", values=["Crash", "Death", "Warn", "Silent"])
for f in ["spring_ball", "yapping_maw", "auto_reserve", "x_mode", "sprite_overflow"]:
    add(G, "crash_fix_" + f, CRASH + f, "choice")
add(G, "fix_blue_echoes", QOL + "fix_blue_echoes", "toggle")
add(G, "ammo_refill_all", QOL + "ammo_refill_all", "toggle")
add(G, "energy_station_reserves", QOL + "energy_station_reserves", "toggle")
add(G, "etank_refill", QOL + "etank_refill", "choice")
add(G, "disableable_etanks", QOL + "disableable_etanks", "choice")
add(G, "reserve_backward_transfer", QOL + "reserve_backward_transfer", "toggle")
add(G, "enemy_drops", QOL + "enemy_drops", "choice")
add(G, "early_save", QOL + "early_save", "toggle")
add(G, "persist_flash_suit", QOL + "persist_flash_suit", "toggle")
add(G, "persist_blue_suit", QOL + "persist_blue_suit", "toggle")
add(G, "camera_fixes", QOL + "camera_fixes", "toggle")

G = "Objectives"
OBJECTIVES = [("Kraid", "kraid"), ("Phantoon", "phantoon"), ("Draygon", "draygon"), ("Ridley", "ridley"),
              ("SporeSpawn", "spore_spawn"), ("Crocomire", "crocomire"), ("Botwoon", "botwoon"),
              ("GoldenTorizo", "golden_torizo"), ("MetroidRoom1", "metroid_room_1"),
              ("MetroidRoom2", "metroid_room_2"), ("MetroidRoom3", "metroid_room_3"),
              ("MetroidRoom4", "metroid_room_4"), ("BombTorizo", "bomb_torizo"), ("BowlingStatue", "bowling_statue"),
              ("AcidChozoStatue", "acid_chozo_statue"), ("PitRoom", "pit_room"), ("BabyKraidRoom", "baby_kraid_room"),
              ("PlasmaRoom", "plasma_room"), ("MetalPiratesRoom", "metal_pirates_room")]
for obj, n in OBJECTIVES:
    add(G, "objective_" + n, "objective_settings.objective_options", "objective", objective=obj)
add(G, "min_objectives", "objective_settings.min_objectives", "int", min=0, max=19)
add(G, "max_objectives", "objective_settings.max_objectives", "int", min=0, max=19)
add(G, "objective_screen", "objective_settings.objective_screen", "choice")

G = "Map and Doors"
add(G, "map_layout", "map_layout", "choice")
for color in ["red", "green", "yellow", "charge", "ice", "wave", "spazer", "plasma"]:
    add(G, f"{color}_doors_count", f"doors_settings.{color}_doors_count", "int", min=0, max=100)
add(G, "area_assignment", AREA + "preset", "sub_preset", values=["Standard", "Size", "Depth", "Random"])
add(G, "area_assignment_base_order", AREA + "base_order", "choice")
add(G, "ship_in_crateria", AREA + "ship_in_crateria", "toggle")
add(G, "mother_brain_in_tourian", AREA + "mother_brain_in_tourian", "toggle")
add(G, "door_locks_size", OTHER + "door_locks_size", "choice")

G = "Start Location"
add(G, "start_location", "start_location_settings.mode", "choice")
add(G, "custom_start_location", "start_location_settings.room_id", "start_location_name")

G = "Game Variations"
add(G, "save_animals", "save_animals", "choice")
add(G, "wall_jump", OTHER + "wall_jump", "choice")
add(G, "speed_booster", OTHER + "speed_booster", "choice")
for f in ["energy_free_shinesparks", "all_enemies_respawn", "disable_spikesuit", "disable_bluesuit",
          "enable_major_glitches"]:
    add(G, f, OTHER + f, "toggle")
add(G, "savestate", OTHER + "savestate", "choice")
add(G, "race_mode", OTHER + "race_mode", "toggle")


# Customize (cosmetic) settings: (option name, field, kind, extras)
CUSTOMIZE = []


def cadd(group, name, field, kind, **extra):
    CUSTOMIZE.append(dict(group=group, name=name, field=field, kind=kind, **extra))


G = "Cosmetics"
cadd(G, "samus_sprite", "samus_sprite", "choice")
cadd(G, "etank_color", "etank_color", "etank_color")
cadd(G, "room_theming", "room_theming", "choice")
cadd(G, "room_palettes", "room_palettes", "theming_choice")
cadd(G, "tile_theme", "tile_theme", "theming_choice")
cadd(G, "door_theme", "door_theme", "choice")
cadd(G, "music", "music", "choice")
cadd(G, "shaking", "shaking", "choice")
cadd(G, "flashing", "flashing", "choice")
cadd(G, "disable_beeping", "disable_beeping", "bool")
cadd(G, "reserve_hud_style", "reserve_hud_style", "bool")
cadd(G, "screw_attack_animation", "vanilla_screw_attack_animation", "choice")
cadd(G, "room_names", "room_names", "bool")
cadd(G, "map_theme", "map_theme", "choice")
cadd(G, "item_dot_change", "item_dot_change", "choice")
cadd(G, "transition_letters", "transition_letters", "bool")
cadd(G, "boss_icons", "boss_icons", "bool")
cadd(G, "miniboss_icons", "miniboss_icons", "bool")
cadd(G, "save_icons", "save_icons", "bool")
cadd(G, "statues_hallway_tiling", "statues_hallway_tiling", "choice")
cadd(G, "statues_hallway_audio", "statues_hallway_audio", "choice")
G = "Controller"
for f in ["shot", "jump", "dash", "item_select", "item_cancel", "angle_up", "angle_down"]:
    cadd(G, "control_" + f, "control_" + f, "choice")
for f in ["spin_lock", "quick_reload", "save_state", "load_state"]:
    cadd(G, f + "_buttons", f + "_buttons", "buttons", prefix=f + "_")
cadd(G, "moonwalk", "moonwalk", "bool")

BUTTONS = ["Left", "Right", "Up", "Down", "X", "Y", "A", "B", "L", "R", "Select", "Start"]


# ---------------------------------------------------------------------------------------------------------------------

def choices_of(entry):
    """Choices of a setting: the values defined by Map Rando, in the website's order (and only those offered by the
    website, when the website lists them)."""
    path = entry["path"]
    if path == "map_layout":
        rust_values = upstream_data.map_layouts()
    elif path in LIST_ENUMS:
        rust_values = RUST_ENUMS[LIST_ENUMS[path]]
    elif path in SCHEMA and SCHEMA[path][0] == "enum":
        rust_values = SCHEMA[path][1]
    else:
        return [c for c in entry.get("choices") or [] if c["value"] is not None]
    website = [c for c in entry.get("choices") or [] if c["value"] is not None]
    unknown = [c["value"] for c in website if c["value"] not in rust_values]
    if unknown:
        raise SystemExit(f"Website choices {unknown} for {path} are not Map Rando values {rust_values}")
    if not website:
        return [{"value": v, "label": v} for v in rust_values]
    hidden = [v for v in rust_values if v not in [c["value"] for c in website]]
    if hidden:
        WARNINGS.append(f"{path}: values {hidden} are not offered on the website (not exposed)")
    return website


def gen_category(spec):
    e = RS[spec["path"]]
    cn = class_name(spec["name"])
    lines = [f"class {cn}(PresetChoice):\n"]
    extra = ("The preset for this category of settings, as on the maprando.com website. 'preset' keeps the "
             "category from the selected settings preset (settings_preset). Individual settings of the category can "
             "still be changed with the options below.")
    if spec["name"] == "skill_assumptions_preset":
        extra += "\nImplicit and Beyond are not offered on the website, but are valid Map Rando presets."
    lines.append(docstring(e["label"], e["description"], extra))
    lines.append(f'    display_name = "{e["label"]}"\n')
    lines.append(f'    path = "{spec["path"]}"\n')
    lines.append(f'    preset_dir = "{spec.get("preset_dir", "")}"\n')
    json_values = {}
    for i, v in enumerate(upstream_data.preset_names(PRESET_CATEGORIES[spec["preset_dir"]]), start=1):
        k = key_for(v)
        lines.append(f"    option_{k} = {i}\n")
        json_values[i] = v
    lines.append(f"    json_values = {json_values!r}\n")
    return cn, "".join(lines)


def gen_setting(spec):
    path = spec["path"]
    kind = spec["kind"]
    cn = class_name(spec["name"])
    if kind == "objective":
        e = RS[path]
        obj = spec["objective"]
        label = f"Objective: {dict((o, n) for o, n in OBJECTIVES)[obj].replace('_', ' ').title()}"
        desc = ("Whether this objective is required to open the way to Mother Brain: No (never), Maybe (may be "
                "randomly selected, up to the number of objectives), or Yes (always).\n" + e["description"])
        lines = [f"class {cn}(PresetChoice):\n", docstring(label, desc, PRESET_NOTE),
                 f'    display_name = "{label}"\n', f'    path = "{path}"\n', f'    objective = "{obj}"\n']
        jv = {}
        for i, c in enumerate(choices_of(e), start=1):
            lines.append(f"    option_{key_for(c['value'])} = {i}\n")
            jv[i] = c["value"]
        lines.append(f"    json_values = {jv!r}\n")
        return cn, "".join(lines)
    e = RS[path]
    label = e["label"]
    if spec["name"].startswith(("enhanced_map_", "initial_map_reveal_", "map_station_activation_", "crash_fix_")) \
            and kind != "sub_preset":
        prefix = {"enhanced_map_": "Enhanced map", "initial_map_reveal_": "Initial map reveal",
                  "map_station_activation_": "Map station activation", "crash_fix_": "Crash fix"}
        for p, title in prefix.items():
            if spec["name"].startswith(p):
                label = f"{title}: {label}"
                break
    if kind == "sub_preset":
        base = "PresetChoice"
        extra = ("A preset for this group of settings. 'preset' keeps the group from the selected category preset; "
                 "the individual settings below can still be changed.")
        lines = [f"class {cn}({base}):\n", docstring(label, e["description"], extra),
                 f'    display_name = "{label}"\n', f'    path = "{path}"\n']
        jv = {}
        values = [c["value"] for c in choices_of(e)] if SCHEMA[path][0] == "enum" else spec["values"]
        for i, v in enumerate(values, start=1):
            lines.append(f"    option_{key_for(v)} = {i}\n")
            jv[i] = v
        lines.append(f"    json_values = {jv!r}\n")
        return cn, "".join(lines)
    if kind == "choice":
        lines = [f"class {cn}(PresetChoice):\n", docstring(label, e["description"], PRESET_NOTE),
                 f'    display_name = "{label}"\n', f'    path = "{path}"\n']
        jv = {}
        for i, c in enumerate(choices_of(e), start=1):
            lines.append(f"    option_{key_for(c['value'])} = {i}\n")
            jv[i] = c["value"]
        lines.append(f"    json_values = {jv!r}\n")
        return cn, "".join(lines)
    if kind == "toggle":
        return cn, "".join([f"class {cn}(PresetToggle):\n", docstring(label, e["description"], PRESET_NOTE),
                            f'    display_name = "{label}"\n', f'    path = "{path}"\n'])
    if kind == "int":
        return cn, "".join([f"class {cn}(PresetRange):\n",
                            docstring(label, e["description"],
                                      f"Range: {spec['min']} to {spec['max']}. {PRESET_NOTE}"),
                            f'    display_name = "{label}"\n', f'    path = "{path}"\n',
                            f"    range_start = {spec['min']}\n", f"    range_end = {spec['max']}\n"])
    if kind == "float":
        # NamedRange requires range_start <= -1 for the "preset" special value; floats are free text.
        lines = [f"class {cn}(PresetFloat):\n",
                 docstring(label, e["description"],
                           f"A number from {spec['min']} to {spec['max']} (decimals allowed). {PRESET_NOTE}"),
                 f'    display_name = "{label}"\n', f'    path = "{path}"\n',
                 f"    min_value = {float(spec['min'])!r}\n", f"    max_value = {float(spec['max'])!r}\n"]
        if spec.get("integer_valued"):
            lines.append("    integer_valued = True\n")
        return cn, "".join(lines)
    raise ValueError(kind)


def gen_special(spec):
    """Tech/notables, item pool, starting items, priorities, custom start location."""
    name, kind, path = spec["name"], spec["kind"], spec["path"]
    cn = class_name(name)
    e = RS[path]
    if kind == "tech":
        groups = e["groups"]
        enabled = name == "tech_enabled"
        verb = "enable" if enabled else "disable"
        desc = (f"Tech (techniques) to {verb}, in addition to those of the selected skill assumptions preset. "
                f"Tech can be given by name (as in the logic pages of maprando.com, e.g. canWallJump), or a "
                f"difficulty tier name ({', '.join(g['difficulty'] for g in groups)}) to {verb} all tech of that "
                f"tier." + ("" if enabled else " Disabling takes precedence over enabling."))
        keys = sorted({t["name"] for g in groups for t in g["tech"]} | {g["difficulty"] for g in groups})
        return cn, "".join([f"class {cn}(OptionSet):\n", docstring("Tech " + ("enabled" if enabled else "disabled"),
                                                                       desc, clean(e["description"])),
                            f'    display_name = "{"Enabled" if enabled else "Disabled"} tech"\n',
                            f'    path = "{path}"\n', f"    valid_keys = {keys!r}\n"])
    if kind == "notables":
        groups = e["groups"]
        enabled = name == "notables_enabled"
        verb = "enable" if enabled else "disable"
        desc = (f"Notable strats to {verb}, in addition to those of the selected skill assumptions preset. A "
                f"notable is given as 'Room Name: Notable Name' (as listed on maprando.com, e.g. "
                f"'Crab Hole: Gravity Space Jump Climb'), or a difficulty tier name "
                f"({', '.join(g['difficulty'] for g in groups)}) to {verb} all notables of that tier."
                + ("" if enabled else " Disabling takes precedence over enabling."))
        keys = sorted({f"{n['room_name']}: {n['notable_name']}" for g in groups for n in g["notables"]}
                      | {g["difficulty"] for g in groups})
        return cn, "".join([f"class {cn}(OptionSet):\n",
                            docstring("Notables " + ("enabled" if enabled else "disabled"), desc),
                            f'    display_name = "{"Enabled" if enabled else "Disabled"} notables"\n',
                            f'    path = "{path}"\n', f"    valid_keys = {keys!r}\n"])
    if kind in ("item_pool", "starting_items"):
        items = e.get("items") or []
        return cn, "".join([f"class {cn}(OptionCounter):\n",
                            docstring(e["label"], e["description"],
                                      "Counts given here override those of the preset (item_pool_preset / "
                                      "starting_items_preset); items not listed keep the preset's count. Unique "
                                      "items have a count of 0 or 1." if kind == "item_pool" else
                                      "Counts given here override those of the preset (starting_items_preset); "
                                      "items not listed keep the preset's count. These are Map Rando's own "
                                      "starting items, built into the ROM (unlike Archipelago's start_inventory)."),
                            f'    display_name = "{e["label"]}"\n', f'    path = "{path}"\n',
                            "    valid_keys = ITEM_SETTING_KEYS\n", "    min = 0\n", "    max = 1099\n"])
    if kind in ("key_item_priority", "filler_items"):
        allowed = [c["value"] for c in choices_of(e)]
        return cn, "".join([f"class {cn}(ChoiceMapping):\n",
                            docstring(e["label"], e["description"],
                                      f"Given as a mapping of item name to one of: {', '.join(allowed)}. Items not "
                                      f"listed keep the value from the item progression preset."),
                            f'    display_name = "{e["label"]}"\n', f'    path = "{path}"\n',
                            "    valid_keys = ITEM_SETTING_KEYS\n", f"    allowed_values = {tuple(allowed)!r}\n"])
    if kind == "start_location_name":
        return cn, "".join([f"class {cn}(FreeText):\n",
                            docstring("Custom start location",
                                      "The start location used when start_location is 'custom', by name (one of "
                                      "the Map Rando start locations, e.g. 'Landing Site' or 'Bomb Torizo Room'; "
                                      "see the start location list on maprando.com). Ignored otherwise.\n" +
                                      clean(e["notes"]).split(". Source")[0]),
                            '    display_name = "Custom start location"\n', '    default = ""\n'])
    raise ValueError(kind)


def gen_customize(spec):
    field, kind, name = spec["field"], spec["kind"], spec["name"]
    cn = class_name(name)
    if kind == "buttons":
        prefix = spec["prefix"]
        e = CS[prefix + "left"]
        default = sorted(b for b in BUTTONS if CS.get(prefix + b.lower(), {}).get("default"))
        label = e["label"].split(":")[0]
        return cn, "".join([f"class {cn}(OptionSet):\n",
                            docstring(f"{label} button combination",
                                      f"Buttons to press simultaneously for {label.lower()}. " +
                                      clean(CS[prefix + "left"]["description"])),
                            f'    display_name = "{label} buttons"\n', f'    field = "{field}"\n',
                            f"    valid_keys = {BUTTONS!r}\n", f"    default = frozenset({default!r})\n"])
    e = CS[field]
    if kind == "bool":
        base = "DefaultOnToggle" if e["default"] else "Toggle"
        return cn, "".join([f"class {cn}({base}):\n", docstring(e["label"], e["description"]),
                            f'    display_name = "{e["label"]}"\n', f'    field = "{field}"\n'])
    if kind == "etank_color":
        lines = [f"class {cn}(TextChoice):\n",
                 docstring(e["label"], e["description"],
                           "One of the website's colors (by hex RGB code), or any other hex RGB code such as "
                           "'ff0000'."),
                 f'    display_name = "{e["label"]}"\n', f'    field = "{field}"\n']
        default = None
        for i, c in enumerate(choices_of(e)):
            lines.append(f"    option_{c['value'].lower()} = {i}\n")
            if c["value"].lower() == str(e["default"]).lower():
                default = i
        lines.append(f"    default = {default}\n")
        return cn, "".join(lines)
    if kind in ("choice", "theming_choice"):
        choices = choices_of(e)
        extra = ""
        lines = []
        jv = {}
        offset = 0
        if kind == "theming_choice":
            extra = "'room_theming' (the default) uses the value given by the room_theming option."
            lines.append("    option_room_theming = 0\n")
            jv[0] = None
            offset = 1
        default_index = None
        for i, c in enumerate(choices, start=offset):
            k = key_for(c["label"] if isinstance(c["value"], bool) else c["value"])
            lines.append(f"    option_{k} = {i}\n")
            jv[i] = c["value"]
            if c["value"] == e.get("default"):
                default_index = i
        if kind == "theming_choice":
            default_index = 0
        if name == "screw_attack_animation":
            extra = "Vanilla: the Screw Attack animation always looks like Space Jump. Split (default): it depends."
        body = [f"class {cn}(Choice):\n",
                docstring(e["label"], e["description"] +
                          ("\nSprites: " + ", ".join(f"{c['value']} ({c['label']})" for c in choices)
                           if name == "samus_sprite" else ""), extra),
                f'    display_name = "{e["label"]}"\n', f'    field = "{field}"\n'] + lines + [
                   f"    default = {default_index}\n", f"    json_values = {jv!r}\n"]
        return cn, "".join(body)
    raise ValueError(kind)


HEADER = '''"""
Options for Super Metroid Map Rando Upstream.

This file is generated by tools/gen_options.py from the maprando.com website's settings (labels and help texts); edit
the generator rather than this file. The AP-specific options are in ap_options.py.
"""
from __future__ import annotations

from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, FreeText, OptionCounter, OptionSet, PerGameCommonOptions, \\
    StartInventoryPool, TextChoice, Toggle

from .ap_options import CommonDoorColors, CommonMap, DeathLink, ItemMatching, LocalEarlyProgression, \\
    MapRandoSettings, RemoteItems, UniqueStartLocations
from .option_types import ChoiceMapping, PresetChoice, PresetFloat, PresetRange, PresetToggle

# Map Rando item names (as used in Map Rando's settings), accepted by the item settings options
ITEM_SETTING_KEYS = {item_keys!r}

'''


def upstream_items():
    """Map Rando's items (the Item enum of maprando-game), in order."""
    src = open(os.path.join(ROOT, "MapRandomizer", "rust", "maprando-game", "src", "lib.rs"), encoding="utf-8").read()
    for name, body in rust_schema._blocks(rust_schema._strip_comments(src), "enum"):
        if name == "Item":
            return re.findall(r"(\w+)\s*,", body)
    raise SystemExit("Item enum not found")


def check_coverage():
    """Every Map Rando setting must have an option: settings added upstream get one automatically."""
    covered = {spec["path"] for spec in SPEC} | NOT_OPTIONS
    for spec in SPEC:
        if spec["path"] not in SCHEMA:
            raise SystemExit(f"Option {spec['name']}: setting {spec['path']} no longer exists in Map Rando's settings.rs")
    for path, (kind, detail) in SCHEMA.items():
        if path in covered:
            continue
        name = "_".join(path.split(".")[-2:]) if path.count(".") >= 2 else path.split(".")[-1]
        auto = {"group": "Other Map Rando Settings", "name": name, "path": path}
        if kind == "bool":
            auto["kind"] = "toggle"
        elif kind == "enum":
            auto["kind"] = "choice"
        elif kind == "int":
            auto.update(kind="int", min=0, max=1000)
        elif kind == "float":
            auto.update(kind="float", min=0, max=1000)
        else:
            raise SystemExit(f"New Map Rando setting {path} ({kind} {detail}) needs to be added to gen_options.py")
        WARNINGS.append(f"new Map Rando setting {path}: added option {name} automatically (review its name/range)")
        SPEC.append(auto)


def gen_settings_preset():
    names = upstream_data.preset_names("full")
    lines = ["class SettingsPreset(Choice):\n",
             docstring("Settings preset", RS["name"]["description"],
                       "The settings preset is the base for all settings: the category presets and individual settings "
                       "below are applied on top of it, wherever they are set to something other than 'preset'."),
             '    display_name = "Settings preset"\n']
    for i, n in enumerate(names):
        lines.append(f"    option_{key_for(n)} = {i}\n")
    lines.append("    default = 0\n")
    lines.append(f"    preset_names = {dict(enumerate(names))!r}\n")
    return "".join(lines), names


def main():
    check_coverage()
    settings_preset_code, full_names = gen_settings_preset()
    classes = [settings_preset_code]
    fields = []
    groups = {}
    for spec in SPEC:
        if spec["kind"] == "category":
            cn, code = gen_category(spec)
        elif spec["kind"] in ("tech", "notables", "item_pool", "starting_items", "key_item_priority",
                              "filler_items", "start_location_name"):
            cn, code = gen_special(spec)
        else:
            cn, code = gen_setting(spec)
        classes.append(code)
        fields.append((spec["name"], cn))
        groups.setdefault(spec["group"], []).append(cn)
    for spec in CUSTOMIZE:
        cn, code = gen_customize(spec)
        classes.append(code)
        fields.append((spec["name"], cn))
        groups.setdefault(spec["group"], []).append(cn)

    item_keys = [i for i in upstream_items() if i != "Nothing"]
    out = [HEADER.format(item_keys=item_keys)]
    for code in classes:
        out.append("\n" + code + "\n")
    out.append("\n@dataclass\nclass SMMROptions(PerGameCommonOptions):\n")
    ap_fields = [("start_inventory_from_pool", "StartInventoryPool"), ("death_link", "DeathLink"),
                 ("remote_items", "RemoteItems"), ("item_matching", "ItemMatching"), ("common_map", "CommonMap"),
                 ("common_door_colors", "CommonDoorColors"), ("unique_start_locations", "UniqueStartLocations"),
                 ("local_early_progression", "LocalEarlyProgression"),
                 ("settings_preset", "SettingsPreset"), ("map_rando_settings", "MapRandoSettings")]
    for name, cn in ap_fields + fields:
        out.append(f"    {name}: {cn}\n")
    out.append("\n\n# Option groups (for the website options page), in display order\n")
    out.append("OPTION_GROUP_CLASSES = {\n")
    for g, cns in groups.items():
        out.append(f"    {g!r}: [{', '.join(cns)}],\n")
    out.append("}\n")
    out.append("\n# The website's full settings presets, for the Archipelago website's options presets\n")
    out.append("FULL_PRESET_OPTIONS = {\n")
    for n in full_names:
        out.append(f"    {n!r}: {{'settings_preset': {key_for(n)!r}}},\n")
    out.append("}\n")
    index = {"full": full_names, "items": upstream_items(),
             "categories": {key: upstream_data.preset_names(key) for key in PRESET_CATEGORIES.values()},
             "map_layouts": upstream_data.map_layouts()}
    with open(PRESETS_INDEX, "w") as f:
        json.dump(index, f, indent=1)
    for w in WARNINGS:
        print("warning:", w)
    with open(OUT, "w") as f:
        f.write("".join(out))
    print(f"Wrote {OUT}: {len(fields)} Map Rando options")


if __name__ == "__main__":
    main()
