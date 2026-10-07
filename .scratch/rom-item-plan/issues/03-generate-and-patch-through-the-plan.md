# 03: Generate and patch through the ROM item plan, with the new patch format

**Spec:** docs/specs/rom-item-plan.md

**What to build:** switch generation and patching to the ROM item plan, end to end, as described in the spec's
"Callers after the change" and "Patch file format" sections. The World builds the planner's inputs from the
`MultiWorld`, calls `plan_rom_items`, and logs the warning when players are dropped; `get_item_placement_and_ap_data`
is deleted. `build_ap_data` only serializes the plan (player names are resolved by the World, and `Rom` stops
importing the World type). `apply_archipelago` loses `base_rom`, writes rows exactly as given, and rejects an old-format
`"ap"` block (any `null` item id) with the spec's clear error. A seed with more than 202 players in the table now
generates instead of crashing.

**Blocked by:** 01 (ROM item plan: a pure planner), 02 (Generation covers `generate_output`)

**Status:** ready-for-agent

- [ ] The World uses `plan_rom_items`; `get_item_placement_and_ap_data` is gone
- [ ] `build_ap_data(plan, player_names, own_player, death_link, remote_items)` only serializes; `Rom` no longer
      imports the World type
- [ ] `apply_archipelago(rom, ap, rom_name)` writes item ids as given and rejects `null` item ids with the spec's error
- [ ] `test_rom.py` builds a plan, serializes it with `build_ap_data`, and checks the bytes `apply_archipelago` writes;
      the base-ROM PLM writes in `synthetic_roms` and the hand-built tuples are deleted
- [ ] `test_rom.py` covers the old-format rejection
- [ ] `test_rom_integration.py` uses the plan instead of `x[2] == 22 and x[1] == 0`
- [ ] The generation test from 02 still passes
