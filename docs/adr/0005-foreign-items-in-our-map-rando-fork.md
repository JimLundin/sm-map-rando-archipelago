# 0005: Off-world items are foreign items, in our fork of Map Rando

Status: accepted (2026-10). Supersedes ADR 0003's send half (Nothing items), and ADR 0002's "unmodified".

## Context

ADR 0003 showed an off-world item as Map Rando's Nothing, assuming its pickup sets the collected bit. It doesn't:
Map Rando draws Nothing as a Missile tank PLM and copies the Nothing locations' bits into a new save's collected
bits (`nothing_item_bitmask`, `new_game.asm`). In the emulator, every Nothing location is collected from the first
frame: it never appears, and the client would send all of them at once.

Showing something else there means changing how Map Rando places items (the private `Patcher::place_items`), its map
markers and its PLMs, which we can't do from outside the crate.

## Decision

- The `MapRandomizer` submodule is our fork (JimLundin/MapRandomizer, branch `foreign-item`): upstream plus a
  foreign item patch, kept small and in Map Rando's style so it could be proposed upstream
  (`docs/specs/foreign-items.md`). Our own code stays out of the fork.
- An off-world item is a **foreign item**: `Randomization.foreign_items` lists its location and class
  (progression, useful, filler), and its `item_placement` entry stays Nothing. The ROM shows a collectible item
  there; its pickup sets the location's collected bit and calls `foreign_item_hook`. The client reads the bits as
  before (ADR 0003).
- `core.mwplan` emits the foreign items, with the class from the Archipelago item's classification.
- Receiving is unchanged (ADR 0003).

## Consequences

- Off-world items can be seen and picked up, and the map marks them by class.
- A Map Rando update is a rebase of the fork branch onto the new upstream, then `make data fixtures`.
- `foreign_item.asm` takes most of the free bank $84 space; our `call_plm_setup` moved to $84:F375 (ABI version 2).
- Picking one up shows who gets what ("ALICE - HOOKSHOT") in a message box, after the item fanfare as Map Rando's
  setting has it. The message font has A-Z, 0-9, space and . - ? !; `core.mwplan.message_text` maps names to it.
