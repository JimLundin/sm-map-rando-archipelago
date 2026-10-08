# 0006: Logic from Map Rando's own traversal, asked from scratch per inventory

Status: accepted (2026-10). Supersedes ADR 0004 (step logic).

## Context

ADR 0004 took the rules from Map Rando's placement steps: sound, but every step required all items of the earlier
steps, so the fill needed help (step order, the narrow steps kept local). The engine can now answer Map Rando's own
question directly (`reach`, docs/specs/logic-oracle.md): with these items of ours, which item locations can Samus
reach and come back from, and can she defeat Mother Brain. It agrees with Map Rando's placement step by step on the
recorded seed and in 74 of 80 random settings; the rest differ by a step, because Map Rando's traversal keeps at most
four states per vertex and continues from step to step.

## Decision

- Generation asks the engine for a world (`world`: map, doors, objectives, start; no placement) and opens a session
  on it. Archipelago places all of our items.
- Every location's rule asks the oracle, with the counts of our collected items, whether the location is reachable;
  Victory asks whether Mother Brain can be defeated. `core.logic.Oracle` caches the answers by those counts.
- Each answer is a fresh traversal (option 1 of the spec). Flags that strats negate (Phantoon, Kraid, ...) are set in
  a second stage, after everything else settled, so "before those bosses" is a play order too.
- Every item the logic counts is progression (tanks and ammo skip balancing); Nothing is filler. Regions only group
  locations by area.
- Some starts reach a single location with no items, where Archipelago's fill can corner itself (1 in 24 seeds
  failed). While fewer than 4 of our locations are reachable, `pre_fill` places the item of ours that opens the most
  locations at one of them, as Map Rando's own placement does in its first steps.
- The patch carries the world and the placement; the engine builds the `Randomization` from them.

## Consequences

- The rules are Map Rando's logic, not an under-approximation of its placement order: no step order, and only the
  first few locations of a tight start kept local (the `local_early_progression` option is gone).
- A fresh traversal is rarely non-monotone (3 in 80 seeds lost a location with more items), which Archipelago assumes
  can't happen: at worst a fill or accessibility check fails. Every reported location is reachable.
- Speed: a fill asks ~300 inventories, ~0.15 s each when nearly everything is collected: ~40 s per Map Rando world.
  Faster answers (inference from cached inventories, warm starts) and history-keeping answers (option 2) stay inside
  `Oracle` and the engine; the World doesn't change.
