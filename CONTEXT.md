# Domain glossary

Terms used across the Super Metroid Map Rando world. Keep code, docs and reviews consistent with these.

**Item location** — one of Map Rando's 100 item locations. It has three identities:
- `index`, its position in Map Rando's `item_placement`
- `(room_id, node_id)`, as used in the spoiler summary
- `bit_index`, which is the ROM's index and the Archipelago location id minus 86000

**Off-world item** — an item at one of our locations that isn't shown as a Map Rando item: either no Map Rando item
matches it, or it is a Nothing that belongs to another player. It is drawn with the Archipelago sprite and gets an
off-world name slot (item ids 25-124) for its message box.

**Map marker** — the Map Rando item an off-world item is shown as on the map: Bombs (progression), ETank (useful) or
Missile (filler).

**Destination** — who receives the item at a location: own (0), another player (1), or an item link that includes us
(2). These values are the ROM ABI.

**Player table** — the up-to-202 player ids and names written into the ROM. It is used for "sent to" and "received
from" messages, and index 0 is "Archipelago".

**ROM item plan** — everything the ROM needs to know about our item locations: the adjusted Map Rando placement, one
row per location, and the player table. It is produced by `plan_rom_items` (see `docs/specs/rom-item-plan.md`).
