# 0004: Logic from Map Rando's placement steps, narrow steps kept local

Status: accepted (2026-10)

## Context

Archipelago needs access rules for our locations. Reimplementing Map Rando's logic (thousands of strats over
sm-json-data) in Python is out of the question, and calling its traversal per AP state is too slow.

## Decision

Map Rando's spoiler summary lists the steps of its own item placement. Step *k*'s locations are reachable with every
item of steps 1..k-1, so each step becomes a region that requires those items (`core.logic`). The rule is sound by
construction. Locations outside the steps (stop-early, escape start) only get filler.

These rules are strict: the earliest steps often have one to three locations. The fill copes in two ways:

- `fill_hook` orders our items and locations by step, so the fill follows Map Rando's order;
- `local_early_progression` (on by default) keeps Map Rando's own item at each location of a step with fewer than 5
  locations (`core.logic.bottleneck_locations`), a placement that is known to work.

## Consequences

- Single-world and multiworld fills succeed reliably (12/12 seeds with three Map Rando worlds in testing).
- Every in-logic item is progression (ammo too), because the rule counts them.
- More permissive logic would need Map Rando's traversal (a future engine command), not more Python.
