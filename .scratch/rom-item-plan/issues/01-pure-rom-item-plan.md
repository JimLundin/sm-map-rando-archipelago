# 01: ROM item plan: a pure planner with a player table that fits

**Spec:** docs/specs/rom-item-plan.md

**What to build:** the pure `rom_items` module described in the spec's Design section: `PlacedItem`, `Destination`,
`RomItem`, `RomItemPlan` and `plan_rom_items`. Given Map Rando's item placement and the item at each of our item
locations, it decides each location's destination, its Map Rando item or map marker, its off-world name slot, and the
player table (following the spec's player table rule). It does not import `BaseClasses` or `MultiWorld` and does no I/O.
`match_item` takes plain values instead of the World, and the World's existing call is updated to match (behaviour
unchanged). Nothing else uses the planner yet; it is verified by its own fast tests.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `plan_rom_items` and its types exist as specified, in a module with no `BaseClasses`/`MultiWorld` import
- [ ] `match_item` no longer takes the World; existing behaviour and tests are unchanged
- [ ] Off-world name slots are assigned in location order from `OFFWORLD_ITEM_FIRST_ID`, with an assert that they fit
- [ ] The player table keeps 0, ourselves, every receiving player, then senders (lowest ids kept), sorted by id, at
      most `ROM_PLAYERDATA_COUNT` entries; `dropped_players` counts the senders that didn't fit
- [ ] New `test_rom_items.py` covers every planner case in the spec's Tests section, including the 300-sender
      regression and 100 off-world items, and needs no `MultiWorld`, ROM or native module
