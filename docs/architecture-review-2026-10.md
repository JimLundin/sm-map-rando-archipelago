# Architecture review — October 2026

Deepening opportunities found in the Super Metroid Map Rando world (`worlds/sm_map_rando`), its build tools and the
native module. Vocabulary: **module**, **interface**, **implementation**, **depth** (deep/shallow), **seam**,
**adapter**, **leverage**, **locality**.

| | Candidate | Strength | Dependency category |
|---|---|---|---|
| A | Put a real seam in front of the Rust randomizer | Strong | ports & adapters |
| B | Keep the option kind; let each option apply itself | Strong | in-process |
| C | Plan ROM items as a typed, pure module | Strong | in-process |
| D | One ROM layout module, fed by the assembler | Worth exploring | in-process + build-time |
| E | Pull shared-map generation out of the World | Worth exploring | ports & adapters (needs A) |
| F | One version source, checked at release | Worth exploring | build-time |
| G | Let Rust own the Map Rando facts Python copies | Speculative | local-substitutable |

**Top recommendation: C first, then A.** C is in-process, needs no new seam, fixes a crash nothing tests (below), and
turns code that only a real ROM can exercise into fast table tests. A's fake adapter is what makes E and most of the
World testable.

**Bug found during the review:** `__init__.py:402` slices a `set`, so generation raises `TypeError` when a player
interacts with more than `ROM_PLAYERDATA_COUNT` (202) players. Tracked under C.

---

## A · Put a real seam in front of the Rust randomizer

**Files:** `native.py`, `Rom.py:256`, `__init__.py:183-214`, `test/test_rom_integration.py:32`,
`tools/build_apworld.py:85`, `tools/upstream_data.py:45`, `native/pysmmaprando/src/lib.rs`

**Problem.** `native.py` does four jobs:
- choosing and installing the wheel (`_wheel_platform_tags`, `_find_bundled_wheel`, `_install_bundled_wheel`,
  `get_module`)
- reading world files, with the same zip-or-directory branch written five times
- downloading assets (`ensure_samus_sprite`, `ensure_mosaic_patches`)
- a facade over the randomizer that covers only two of the three Rust calls

`Rom.patch_rom` and `test_rom_integration` go around the facade with `get_map_rando().make_rom(json.dumps(...))`.
The tools create their own `pysmmaprando.MapRando` instances. Wheel selection broke in the 0.123.2 release and still
has no test, and CI skips that code path because it installs the wheel first.

**Solution.**
- A `MapRando` port with three calls: `upgrade_settings`, `randomize` and `make_rom`.
- A native adapter, which is the only code that calls `json.dumps` and `get_map_rando()`.
- A fake adapter that returns canned `rando_output` for tests.
- `select_wheel(names, sys_platform, machine, version)` becomes a pure function.
- File reads use `pkgutil.get_data`, except where Rust needs a real directory.
- Remove the Rust parameters that are never used (`fixed_map_seed`, `display_seed`, `include_spoiler_log`,
  `default_settings`).

**Wins.**
- Two adapters (native and fake) justify the seam.
- Locality: JSON crosses the seam in one place.
- Wheel selection gets table tests.
- World logic can be tested without Rust.
- Five zip-or-directory branches are deleted.

## B · Keep the option kind; let each option apply itself

**Files:** `tools/gen_options.py:120-270`, `Options.py` (generated), `option_types.py`,
`settings_builder.py:144-151, 293-414`, `ap_options.py`, `OptionPresets.py`

**Problem.** The generator knows each option's kind (`category`, `sub_preset`, `objective`, `tech`, `item_pool`, …)
but doesn't write it into `Options.py`. `build_randomizer_settings` then works the kind out again, using:
- `getattr(option, "preset_dir")` and `getattr(option, "objective")`
- path suffix checks (`.preset`, `_preset`)
- a hard-coded list of eight field names

The same facts are copied in several places:
- sub-preset value lists in three places
- item uniqueness in four (`Items.ITEM_DATA`, `UNIQUE_ITEMS`/`MULTI_ITEMS`, `presets_index.json`, `create_item`)
- the list of AP options in three

**Solution.**
- The generator picks an option class by kind.
- Each class implements `MapRandoSetting.apply(settings)`.
- `build_randomizer_settings` becomes: base settings → for each layer, `opt.apply(settings)` → relabel presets.
- Sub-preset names live only in the generated values.
- `OptionPresets.py` fails the deletion test: fold it into the generator's output.

**Wins.**
- The interface shrinks to `apply()`.
- Locality: one kind, one class.
- Each kind can be tested on a plain dict, without a `MultiWorld`.

## C · Plan ROM items as a typed, pure module

See the spec: [`docs/specs/rom-item-plan.md`](specs/rom-item-plan.md).

**Files:** `__init__.py:359-404`, `ItemMatching.py`, `Rom.py:105-124, 213-236`, `test/test_rom.py`,
`test/test_rom_integration.py`

**Problem.** Deciding what each of our item locations shows and gives is spread across three modules:
- `World.get_item_placement_and_ap_data` works out the destination type, matches the item, substitutes map
  markers and collects player ids.
- `Rom.build_ap_data` serializes the result.
- `Rom.apply_archipelago` assigns the off-world name indices.

The three are linked by a six-element positional tuple. The only test of the planning code needs a real ROM, which
CI never provides, so the >202-player crash went unnoticed.

**Solution.**
- A pure `plan_rom_items(...)` with no `MultiWorld` dependency returns a typed `RomItemPlan`.
- The World builds the plan's inputs, and the ROM writer only writes the plan.

**Wins.**
- Fixes the crash.
- Fast table tests for item links, Nothing items and player-table truncation.
- Locality: one format, one owner.
- The unused `base_rom` parameter and the test setup left over from the old interface are deleted.

## D · One ROM layout module, fed by the assembler

**Files:** `Rom.py:28-35`, `Client.py:39-51, 101-105, 166`, `Items.py:43`, `basepatch/romhacks/maprando/main.asm:38-73`,
`mr_itemextras.asm:10`, `common/playertable.asm:4`, `tools/build_basepatch.py:28`, `test/test_rom*.py`

**Problem.** The ROM ABI is copied by hand into Python, asm, tests and tools:

| Fact | Python | asm | tests | tools |
|---|---|---|---|---|
| Nothing item id = 22 | 1 | 2 | 2 | |
| first off-world item id = 25 | 1 | 2 | 1 | |
| 202 player slots | 1 | 2 | | |
| receive-queue address | 1 | 1 | | |
| ROM name address/size | 2 | | | |
| load hook `0x81F0BF` | 1 | 1 | | 1 |
| death-link bits | 3 | | | |

The Client gets some addresses from the symbols file and hard-codes others. A comment in `itemtable.asm` is already
out of date, and the Client has no tests.

**Solution.**
- Export the asm `!define`s into the symbols JSON.
- One `rom_layout` module owns every address and ABI constant.
- Rom and Client import only from `rom_layout`.
- A consistency test checks the symbols against `Items` and `Locations`.

**Wins.**
- Locality: an ABI change is made in one place.
- The Client's byte encoding becomes testable.
- The duplicate asm block is deleted.

## E · Pull shared-map generation out of the World

**Files:** `__init__.py:113-214` (`stage_generate_early`, `randomize_group`, `run_randomizer`),
`test/test_generation.py:50-89`

**Problem.** The World class runs all of this:
- grouping players by `CommonMap`
- checking that layout and area assignment agree
- up to 10 leader attempts, driven by exceptions
- catching any exception from Rust and retrying without the forbidden start locations

None of it can be tested without running the real generator.

**Solution.**
- A generation module with `plan_groups(worlds)` (pure) and `randomize_group(port, members, rng)`, which returns
  outcomes. It is written against A's port.
- The World keeps only the Archipelago hooks.

**Wins.**
- Retry and fallback paths are tested in milliseconds with a fake that fails N times.
- Leverage: reuses A's fake adapter.

## F · One version source, checked at release

**Files:** `WORLD_REVISION`, `tools/prepare_upstream.py:51-68`, `version.py`, `archipelago.json`,
`native/pysmmaprando/Cargo.toml`, `native.py:31,133`, `tools/build_apworld.py:71,124`,
`.github/workflows/build.yml:65`, `release.yml:34`

**Problem.** The version is written into three committed files (Cargo.toml, `version.py`, `archipelago.json`).
CI only warns when generated files are stale, and the release never checks the tag against the version.

**Solution.**
- `version.py` is the only committed generated copy.
- `make_zip` writes `world_version` into the manifest.
- The release fails if the tag doesn't match the version, and CI fails on stale generated files.
- Delete `MAP_RANDO_VERSION`, which nothing reads.
- A test checks that `pysmmaprando.VERSION == WORLD_VERSION`.

## G · Let Rust own the Map Rando facts Python copies

**Files:** `lib.rs:197-235, 405-427`, `tools/catalog/build_catalog.py:326`, `settings_builder.py:34-35, 465-471`,
`tools/upstream_checks.py`

**Problem.** Customize defaults, mosaic themes and item pools are copied by hand from Map Rando. Only eight
fingerprint hashes notice when upstream changes them.

**Solution.**
- Rust exposes `customize_defaults()` and `mosaic_themes()`.
- The generators read them through the native instance on the tools side.
- Fingerprints stay only for rules copied from website JavaScript.

**Cost:** the upstream patch grows with every getter, and it is kept small on purpose.
