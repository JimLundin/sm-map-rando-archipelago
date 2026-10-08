# Foreign items in Map Rando

Status: complete on our fork (JimLundin/MapRandomizer, branch `foreign-item`), used by the world (ADR 0005). An
exploration for a possible upstream PR, not yet proposed.

## Why

An item at one of our locations can belong to another world. Map Rando's "Nothing" can't stand in for it:
`place_items` (patch.rs) makes Nothing a Missile tank PLM and records its item bit in `nothing_item_bitmask`, which
`new_game.asm` copies into the collected-item bits ($7E:D870) of a new save. Nothing is already collected: it never
appears, can't be picked up, and the client would report it as checked on the first gameplay frame. Seen in the
emulator: with Nothing at locations 10, 42 and 77, all three bits are set at the start of a new game.

## Design

- `Randomization.foreign_items: Vec<ForeignItem>` (`#[serde(default)]`): `{location_idx, class, message}`, class
  `Progression | Useful | Filler`. The location's `item_placement` must be `Nothing`, since Samus gets nothing from
  it, so the logic, spoiler and credits stay correct without knowing about foreign items.
- The patcher places a foreign item PLM there instead of Nothing's. It's not added to the Nothing bitmask or count,
  so it's collectible and counts as an item for item %.
- `patches/src/foreign_item.asm`: three PLMs ($F300 plain, $F304 chozo orb, $F308 shot block), copies of Map Rando's
  Spark Booster PLMs. Their graphics are the item's class's: a bright diamond (progression), a ring (useful), a small
  dot (filler), at $89:B800, B900 and BA00. The instruction `load_foreign_gfx` asks bank $94 for the class's
  arguments of $8764 (load item PLM GFX), which stay in bank $84 (the game keeps their address per graphics slot).
  Map Rando's `Item Loading.ips` and `vanilla_bugfixes.asm` repurpose vanilla's long-call PLM instructions
  ($84:86D1-870B), so the instructions are our own. The open PLM loads late like Map Rando's open items
  (`load_plms_early.asm`). The pickup sets the room argument item bit, then calls
  `foreign_item_hook` ($85:A050, JSL, A = the location's item bit, data bank $84), which does nothing by default:
  a ROM that knows more replaces its first four bytes with a JML.
- Message: `ForeignItem.message`, up to 2 rows of 26 characters (A-Z, 0-9, space and . - ? !). The pickup plays the
  item fanfare (with fanfares off, a click and `$05D7` = 2, as `itemsounds.asm`), then shows message box $30: a
  small box drawn by `foreign_item_message_box` ($85:A054, reached through `extended_msg_boxes.asm`, which is
  applied whenever there are foreign items) from the table patch.rs writes at $83:C000 (an entry per foreign item: item
  bit, class, message rows and message). The pickup code is in bank
  $94 ($94:B1B0), the message being shown at $7E:F4E4. Digits are the HUD's, in palette $3800; the font has no
  `,`, `'`, `/` or `:`.
- Map markers: `Randomization::marker_item` maps the class to a stand-in item (progression → a unique item,
  useful → E-Tank, filler → Missile), so each marker setting treats it like that item.
- The item PLM check that decides X-ray visibility (`vanilla_bugfixes.asm`, `check_item_plm`) and the Toilet
  intersection code (`is_item_plm_type`) also accept the foreign item PLMs.
- The patch and the graphics are applied only when there are foreign items. Without them the ROM differs from
  upstream only in the extended `check_item_plm` (17 bytes at $84:8369) and the checksum.

## Verified (emulator, default-vanilla seed)

| Container | Locations | New game | Pickup |
|---|---|---|---|
| plain | 13 | not collected | bit set, hook gets bit 26, equipment/ammo/energy unchanged, PLM deleted |
| chozo orb | 15, 36 | not collected | orb bursts, bit set, hook gets the bit, nothing given |
| shot block | 19, 42 | not collected | bit set, hook gets the bit, nothing given, block reconceals (as vanilla) |

The message box shows from all three containers, in one or two rows. It closes on A after the fanfare as for a
vanilla Missile at the same location: about 5 s with Vanilla fanfares, 3 s with Trimmed, 2 s with Off.

X-ray reveals a foreign item in a shot block where it reveals a vanilla Missile (Billy Mays Room). A foreign item in
the Bomb Torizo Room wakes Bomb Torizo when picked up, as a vanilla item does (with the Chozos objective, the
fight). Each class shows its own graphics.

Each against a control with a vanilla Missile at the same location. The three classes give three different map
tile sets. Pickups were driven by walking (plain) or by setting the PLM's trigger byte ($1D77,x = $FF, as a shot or
touch does). The scratch scripts were in /tmp/fi.

## Not done

- The spoiler map and the credits show the marker item and Nothing.
- Graphics colours: palette 0, as Map Rando's Spark Booster.

## Found on the way (our repo, fixed)

- **Map Rando's self check** (`self_check.asm`) verifies the ROM checksum in idle time and shows "SELF CHECK FAIL"
  if it doesn't match. `core/mwpatch.py` changed the ROM after Map Rando without fixing the checksum, so our ROMs
  showed the error screen after ~12 s of gameplay. `mwpatch.apply` now recomputes it (`tests/rom/test_self_check.py`).
- `mw.asm` put `call_plm_setup` at $84:F300, which `foreign_item.asm` uses. It now runs the setup from bank $A2,
  returning through the RTL that ends the PLM handler ($84:85D9): our patch has no code in bank $84 (ABI version 3).
