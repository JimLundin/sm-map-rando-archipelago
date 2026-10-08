# The world and the logic oracle

Status: spike done (engine commands, contract test, measurements). The Archipelago side is not built yet; it needs
the decision under "Open".

## What Map Rando needs from us

Map Rando never needs to know other games' items: an item for another world is `Nothing` to its logic (and a foreign
item in the ROM, `docs/specs/foreign-items.md`). Its logic only asks which of *our* items, and how many, Samus has.

- `Item`: 25 kinds, numbered as the logic's inventory (`inventory.items[item as usize]`).
- `GlobalState` (maprando-logic): the inventory (one bool per item, capacities from pack counts via `collect`, which
  applies the settings' pack sizes and ammo fraction), the pool's capacities (caps), `flags` (bosses, events,
  objectives, Mother Brain) and `doors_unlocked`.
- Placement (`Randomizer::randomize`) is a private loop around public parts: `determine_start_location`, then steps
  of `update_reachability` (a forward and a reverse traversal from the hub) and placement, then `get_randomization`.
  There are no hooks, and none are needed: we replace the loop.

## Engine commands (`engine/src/world.rs`)

- `world {settings, seed}` → `{world, seed_hash}`: the map, locked doors, objectives, start location and hub, escape
  time, Toilet intersections and save-animals choice; the website's attempt loop up to the placement. A world is kept
  only if something is reachable at the start and, with the whole pool, the game is beatable and Phantoon defeatable
  (Map Rando's own checks). Deterministic; the seed name doesn't use the time (Map Rando's does).
- `reach {settings, world, inventories}` → for each inventory (`{item: count}`, on top of the starting items): the
  bireachable item locations (reach and come back to the hub, which is what Map Rando collects), the one-way ones,
  the flags, and whether Mother Brain can be defeated. One step of Map Rando's loop without placing anything: a
  traversal, then the fixed point of flags and doors. Flags some strat negates (`{"not": flag}`, e.g. Phantoon for
  139 strats of the unpowered Wrecked Ship) are set last, one at a time, so each stage is a play order.
- `rom {settings, world, item_placement, foreign_items}`: the `Randomization` from the world and the placement.

## Contract (tests/engine/test_reach.py, tools/check_reach.py)

Map Rando's step k placed items at the locations reachable with the items of steps before k. On the recorded seed,
`reach` gives exactly those locations at every step. Across 80 random settings on the vanilla map (presets, skill
assumptions, item progression, doors, objectives, Ship and random starts, wall jump), 74 agree exactly. In the other
6, one to three locations come one step earlier or later; continuing the traversal from step to step as Map Rando
does (`"chain": true`) makes every one agree.

The cause: the traversal keeps at most four states per vertex (`NUM_COST_METRICS`), a heuristic, so what it finds
depends on what it found before. Map Rando doesn't see it: a location, once bireachable, stays so. A fresh traversal
can therefore also be **non-monotone**: in 3 of the 80, an extra item lost one to three locations (e.g. Bombs lost
Golden Torizo's Room and the Screw Attack Room: new paths with Bombs displaced the state that reached Golden Torizo).
The game itself is monotone (an extra item never hurts), so this is the search, not the logic.

Every location `reach` reports is reachable: the traversal only follows links whose requirements hold. It can only
miss some.

## Cost

Per query ~17 ms. Setup ~95 ms per settings (difficulty tiers, links) and ~20 ms per world (the Randomizer), plus
parsing the world's JSON. An Archipelago rule that caches by our items' counts needs one query per distinct set of
our items the fill and the playthrough look at: on the order of 100-300 per world, a few seconds.

## Open: how Archipelago uses it

1. **Fresh queries, cached by inventory.** A rule is a pure function of our items: deterministic and simple. Rarely
   non-monotone, which Archipelago assumes isn't the case: at worst a fill or accessibility check fails (and is
   retried); a seed it accepts is still beatable, since every reported location is reachable.
2. **Sticky along the state's history, as Map Rando.** A LogicMixin keeps, per CollectionState, the locations found
   so far and the traversal's progress; collecting an item continues the traversal (`"chain"`). Monotone along a
   history and exactly Map Rando's semantics, but a removal (the fill swaps items) means recomputing from scratch, and
   two orders of the same items can differ.
3. **Monotone closure.** Union the answers of the queried subsets of an inventory. Monotone, but an answer can change
   as more is queried.

Option 1 first, measuring how often a fill hits a non-monotone case; 2 if it matters.
