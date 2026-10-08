# 0003: Send through Nothing items; receive by spawning the item's own PLM

Status: accepted (2026-10)

## Context

A multiworld ROM must (1) tell the client which locations were checked, and (2) give items sent by other worlds.
Basepatch-style designs replace every item PLM with custom ones and reimplement giving each item kind, including
Map Rando's own items (Wall Jump Boots, Spark Booster, Blue Booster) and its pickup behaviour.

## Decision

- **Send:** no code. An item for another world is Map Rando's "Nothing" item at that location. Every pickup sets the
  vanilla item-collected bit (`$7E:D870`, indexed by the PLM's room argument), Nothing included. The client reads the
  bits and maps them to locations with a table the patcher writes into the ROM.
- **Receive:** the client writes one item into a WRAM mailbox `{seq, item, sender}`. A tick hooked in front of the
  PLM handler in the main gameplay loop (`$82:8B71`) spawns that item's **own** Map Rando item PLM on Samus's block,
  with a negative room argument (so no collected bit is set). Once the PLM waits to be touched, the tick jumps it to
  its pickup instructions. Equipment, ammo, fanfare and message box are the game's own. A received count, kept with
  the save file, numbers the items, so a reloaded save asks for what it lacks.
- The asm (`mw/mw.asm`, ~300 bytes) uses only free space from Map Rando's `patches/rom_map`, and is tested in a
  headless emulator (`tests/rom`).

## Consequences

- Off-world items look like Nothing for now. A custom "AP item" graphic and "sent to" message would need PLMs in
  bank $84's small free space, which is a later change.
- Received items show their vanilla message box, without "from player X".
- New Map Rando item kinds work as long as their PLM id is in `plm_by_item`, which follows Map Rando's
  `item_to_plm_type`.
- Note for asm changes: asar sizes `#!define` immediates by value. Use `.w` (as in `cmp.w #!items_count`), or a
  16-bit compare silently becomes an 8-bit one.
