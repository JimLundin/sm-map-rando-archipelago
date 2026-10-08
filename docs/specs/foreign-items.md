# Foreign items in Map Rando

Status: on our fork (JimLundin/MapRandomizer, branch `foreign-item`), used by the world (ADR 0005). An exploration
for a possible upstream PR, not yet proposed.

## Why

An item at one of our locations can belong to another world. Map Rando's "Nothing" can't stand in for it:
`place_items` (patch.rs) makes Nothing a Missile tank PLM and records its item bit in `nothing_item_bitmask`, which
`new_game.asm` copies into the collected-item bits ($7E:D870) of a new save. Nothing is already collected: it never
appears, can't be picked up, and the client would report it as checked on the first gameplay frame. Seen in the
emulator: with Nothing at locations 10, 42 and 77, all three bits are set at the start of a new game.

## Design

- `Randomization.foreign_items: Vec<ForeignItem>` (`#[serde(default)]`): `{location_idx, class}`, class
  `Progression | Useful | Filler`. The location's `item_placement` must be `Nothing`, since Samus gets nothing from
  it, so the logic, spoiler and credits stay correct without knowing about foreign items.
- The patcher places a foreign item PLM there instead of Nothing's. It's not added to the Nothing bitmask or count,
  so it's collectible and counts as an item for item %.
- `patches/src/foreign_item.asm`: three PLMs ($F300 plain, $F304 chozo orb, $F308 shot block), copies of Map Rando's
  Spark Booster PLMs with their own graphics ($89:B800). The pickup sets the room argument item bit, then calls
  `foreign_item_hook` ($85:A050, JSL, A = the location's item bit, data bank $84), which does nothing by default:
  a ROM that knows more replaces its first four bytes with a JML.
- Message: `ForeignItem.message`, up to 2 rows of 26 characters (A-Z, 0-9, space and . - ? !). The pickup plays the
  item fanfare (with fanfares off, a click and `$05D7` = 2, as `itemsounds.asm`), then shows message box $30: a
  small box drawn by `foreign_item_message_box` ($85:A054, reached through `extended_msg_boxes.asm`, which is
  applied whenever there are foreign items) from the table patch.rs writes at $83:C000. The pickup code is in bank
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

Each against a control with a vanilla Missile at the same location. The three classes give three different map
tile sets. Pickups were driven by walking (plain) or by setting the PLM's trigger byte ($1D77,x = $FF, as a shot or
touch does). The scratch scripts were in /tmp/fi.

## Not done or not verified

- Graphic: a placeholder diamond, small and faint on screen. One graphic for all classes; per-class graphics need
  more bank $84 space or a table lookup at load time.
- X-ray reveal of a foreign item in a shot block, and a foreign item in the Bomb Torizo Room with the Chozos
  objective: not tested.
- `load_plms_early.asm` delays open items' loading for nicer scrolling; foreign items aren't delayed (cosmetic,
  same as Spark Booster).
- The spoiler map and the credits show the marker item and Nothing.

## Found on the way (our repo, fixed)

- **Map Rando's self check** (`self_check.asm`) verifies the ROM checksum in idle time and shows "SELF CHECK FAIL"
  if it doesn't match. `core/mwpatch.py` changed the ROM after Map Rando without fixing the checksum, so our ROMs
  showed the error screen after ~12 s of gameplay. `mwpatch.apply` now recomputes it (`tests/rom/test_self_check.py`).
- `mw.asm` put `call_plm_setup` at $84:F300, which `foreign_item.asm` uses; it moved to $84:F375 (ABI version 2).

## Next

- Per-class graphics, and a better graphic.
- The untested cases above.
