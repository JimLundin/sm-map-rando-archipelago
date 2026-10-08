# Domain glossary

Terms used across the Super Metroid Map Rando world. Keep code, docs and reviews consistent with these.

**Stage** — one step of the pipeline, S1 to S6 (see `docs/architecture.md`): a function from one artifact to the next.
S1 options, S2 world (engine), S3 logic, S4 plan, S5 patch (S5a Map Rando's ROM, S5b our multiworld patch),
S6 sync (the client's decisions).

**Artifact** — what passes between stages, serializable as JSON: settings, Seed, LogicModel, MwPlan, the ROM.

**Engine** — `smmr-engine`, our Rust binary over Map Rando (our fork: upstream plus foreign items, ADR 0005). The world
reaches it only through the engine port (`core.engine.Engine`).

**World** — the engine's `world` output: everything Map Rando decides before placing items (map, locked doors,
objectives, start location and hub, escape time), with the item pool and the item locations in the map's rooms.
Archipelago places the items.

**Seed** — the engine's `randomize` output: Map Rando's own placement (`randomization`) and the spoiler's step
summary. Generation doesn't use it; the logic's contract test does.

**Item location** — one of Map Rando's 100 item locations. Its `index` is its position in Map Rando's `item_placement`
and `game_data.item_locations`, and its Archipelago id is `LOCATION_ID_BASE + index`. Its **PLM address** is where its
item PLM is in the ROM, and its **collected bit** is that PLM's room argument.

**Step** — one round of Map Rando's own item placement, from the spoiler summary: its locations are those
reachable with the items of the earlier steps.

**Oracle** — the logic: given the counts of our collected items, the item locations Samus can reach and come back
from (**bireachable**, to the hub) and whether she can defeat Mother Brain; the engine's `reach`, through
`core.logic.Oracle` (ADR 0006).

**Off-world item** — an item at one of our locations that belongs to another world. The ROM shows a foreign item
there.

**Foreign item** — Map Rando's item kind for an off-world item (our fork, ADR 0005): `Randomization.foreign_items`,
at a location whose placement is Nothing. It can be picked up, sets the location's collected bit, gives nothing,
calls `foreign_item_hook` and shows its message ("ALICE - HOOKSHOT"). Its class (progression, useful, filler)
decides its map marker.

**ROM ABI** — `world/smmr/data/abi.toml`: every address and format the patcher, the ROM and the client share. It's the
only copy: the asm defines and `core.abi` come from it.

**Mailbox** — the WRAM words the client writes to give one received item: `seq` (its 1-based number), item and sender.

**Received count** — the number of received items the ROM has given. It's kept with the save file, and the mailbox
holds item number received count + 1.

**Location table** — the ROM table mapping collected bits to item location indexes. The patcher writes it, and the
client reads it once when it connects.

**ROM name** — the 21-byte cartridge title `SMMR<abi version><player><seed>`. It identifies the slot to the client and
the server.

**Category preset** — a Map Rando preset for one settings category (skill assumptions, item progression, quality of
life, objectives, doors), chosen by name. Map Rando's upgrade expands it. A **full preset** sets every category.
