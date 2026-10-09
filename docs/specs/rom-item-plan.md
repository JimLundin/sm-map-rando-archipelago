# Spec: ROM item plan

Status: **draft — decisions settled, ready to implement**. Candidate C of the [October 2026 architecture review](../architecture-review-2026-10.md).

## Goal

All decisions about what each of our 100 item locations shows and gives, and which players appear in the ROM's player
table, live in one deep, pure module with a typed result. The World builds its inputs from the `MultiWorld`; the ROM
writer only writes the result.

## Today

```
World.get_item_placement_and_ap_data()          __init__.py:359-404
  per location: destination type (own / other / item link), match_item(world, item),
                map marker substitution in the Map Rando placement, player ids
  then: players who have items for us, truncation to 202 (crashes: slices a set, line 402)
  → (placement, [(bit_index, dest_type, item_id|None, advancement, item_name, dest_player)], player_ids)

Rom.build_ap_data(world, location_items, player_ids)   Rom.py:105-124
  → player names from the MultiWorld, ids > 65535 → 0, tuples → lists, config flags

Rom.apply_archipelago(rom, base_rom, ap, rom_name)     Rom.py:187-243
  unpacks the 6 positions; assigns off-world name indices (25, 26, …); sets locations_nothing bits;
  base_rom unused
```

Problems:
- **Crash.** With more than 202 players in the table, `set(...)[:n]` raises `TypeError`, so the seed fails to
  generate. No test covers this.
- **No locality.** One decision ("what does this location become in the ROM") is split across three functions in two
  modules. The off-world name numbering is decided while the ROM is being written, not when the plan is made.
- **Untested.** The planning code needs a full `MultiWorld` after fill. Its only test is `test_rom_integration`,
  which also needs a real ROM, and CI never runs it. `test_rom` hand-writes the tuples, so it tests the writer
  against a format that nothing checks against the planner.
- **Interface leaks.** The tuple layout is documented only in a docstring and indexed by position (`x[5]`, `x[2] == 22`).

## Design

### New module: `worlds/sm_map_rando_upstream/rom_items.py`

The module is pure: it does not import `BaseClasses` or `MultiWorld`, and it does no I/O.

```python
@dataclass(frozen=True)
class PlacedItem:
    """An item placed at one of our locations, as far as the ROM cares."""
    name: str
    game: str
    player: int          # receiving player (or item-link group id)
    advancement: bool
    useful: bool

class Destination(IntEnum):     # values are the ROM ABI (rando_item_table)
    OWN = 0
    OTHER = 1
    ITEM_LINK = 2               # an item-link group that includes us

@dataclass(frozen=True)
class RomItem:
    bit_index: int
    destination: Destination
    item_id: int         # Map Rando item id (0-24), or off-world name slot (25-124)
    advancement: bool
    player: int          # receiving player id
    name: str            # message box name (only written for off-world slots)

@dataclass(frozen=True)
class RomItemPlan:
    placement: list[str]        # Map Rando item_placement, with off-world items shown as map markers
    items: list[RomItem]        # one per location, in LOCATIONS order
    players: list[int]          # player table: [0, …], at most ROM_PLAYERDATA_COUNT entries
    dropped_players: int        # received-from players that didn't fit (for the warning)

def plan_rom_items(
    placement: Sequence[str],                 # Map Rando's item_placement
    items: Mapping[int, PlacedItem],          # by location index (LOCATIONS[i]["index"])
    own_player: int,
    own_game: str,
    item_links: Collection[int],              # group ids of item links that include us
    senders: Collection[int],                 # players who have items for us
    metroid_matching: bool,                   # item_matching == metroid
) -> RomItemPlan
```

`plan_rom_items` owns:
1. **Destination type.** `OWN` if `player == own_player`, `ITEM_LINK` if `player in item_links`, otherwise `OTHER`.
2. **Matching.** The rules of `match_item`: our own game's items by name; other Metroid games' items through the
   matching table if `metroid_matching`; Nothing from another player is shown as a generic item.
   `ItemMatching.match_item` takes plain values instead of `world` (its tables don't change).
3. **Map markers.** An unmatched item is shown as `Bombs` if advancement, `ETank` if useful, `Missile` otherwise.
4. **Off-world name slots.** Assigned here: `OFFWORLD_ITEM_FIRST_ID + n`, in location order. With 100 locations, the
   slots can never run out (25 + 100 = `ITEM_NAME_COUNT`). An assert keeps that true.
5. **Player table.** See the next section.

### Player table rule

Players are kept in this priority order:
1. `0` ("Archipelago") at index 0.
2. `own_player`.
3. Every receiving player of our locations, so that "sent to X" messages are always right.
4. Senders, which are only needed for "received from X" names. If space runs out, these are dropped first, and the
   lowest ids are kept.

Groups 1-3 have at most 102 entries (100 locations + 2), which is within 202. So every receiving player always fits,
and the current `else sorted(keep)[:202]` branch is dead and is removed. The table is sorted by id, as it is today.

### Callers after the change

- **World.** It builds `PlacedItem`s from `location.item`, `item_links` from `multiworld.groups`, and `senders` from
  `multiworld.get_locations()`, then calls `plan_rom_items`. If `dropped_players` is non-zero it logs the warning.
  `get_item_placement_and_ap_data` is deleted.
- **`Rom.build_ap_data(plan, player_names, own_player, death_link, remote_items)`** only serializes. The player names
  are resolved by the World, so `Rom` stops importing the World type.
- **`Rom.apply_archipelago(rom, ap, rom_name)`** loses `base_rom` and writes rows exactly as given, without
  assigning any numbers.

### Patch file format (`rando_data.json` → `"ap"`)

The `"locations"` rows keep their six columns, but the item id column always holds an integer: off-world items carry
their slot number, assigned by the planner.

**This breaks the format.** Patch files generated by 0.123.x won't patch with the new version. Archipelago doesn't
check the world version when it applies a patch, so `apply_archipelago` fails clearly instead of writing a broken
ROM. If any item id is `null`, it raises "This patch was generated by an older version of Super Metroid Map Rando Upstream;
regenerate the seed or use the matching version." The release notes say the same.

## Tests

**New: `test/test_rom_items.py`.** These tests run in milliseconds and need no `MultiWorld`, ROM or native module.
- An own item maps to `OWN`, its Map Rando id, and an unchanged placement.
- An item from another Map Rando world maps to `OTHER` and is matched by name.
- An off-world progression, useful or filler item gets the `Bombs`, `ETank` or `Missile` marker respectively, and
  slots 25, 26, … in location order.
- An item-link group that includes us maps to `ITEM_LINK`.
- Nothing from another player is shown as an off-world item, not as id 22.
- With metroid matching on, an SMZ3 `Missile Expansion` is shown as `Missile`; with matching off, as off-world.
- **The player table with 300 senders** (the regression): it has 202 entries; 0, ourselves and all receiving players
  are present; and `dropped_players` = (players + senders) − 202.
- With 100 off-world items, slots 25-124 are used and none collide.
- An old-format `"ap"` block (with `null` item ids) is rejected by `apply_archipelago` with the clear error
  (in `test_rom.py`).

**Changed.**
- `test_rom.py` builds a `RomItemPlan` (or calls `plan_rom_items`), serializes it with `build_ap_data`, then checks
  the bytes `apply_archipelago` writes. This tests the round trip through one format. The base-ROM PLM writes in
  `synthetic_roms` are deleted, because nothing reads them.
- `test_rom_integration.py` uses the plan instead of `x[2] == 22 and x[1] == 0`.
- One generation test (`test_generation.py`) runs `generate_output` in a temporary directory, so the World's input
  building is covered in CI.

**Deleted:** the hand-built six-element tuples.

## Out of scope

- Moving the ROM constants (`ROM_PLAYERDATA_COUNT`, `NOTHING_INDEX`, `OFFWORLD_ITEM_FIRST_ID`) into one layout module.
  That is candidate D, and this module imports them from where they are today.
- The native seam (candidate A).

## Decisions

1. **Patch compatibility.** The format change is allowed to break old files: 0.123.x patch files are rejected with
   a clear error, and they are not kept working.
2. **Which senders to drop.** The lowest ids (today's intended behaviour).
3. **Module name.** `rom_items.py`, matching the newer lowercase modules.
