# Super Metroid Map Rando Upstream

## What is this game?

[Super Metroid Map Rando](https://maprando.com) is a Super Metroid randomizer that randomizes the map: how the rooms
connect to each other, and which area each room belongs to. On top of that, it randomizes item locations, door colors,
objectives, the start location, and more. Its logic is based on the community-maintained
[sm-json-data](https://github.com/vg-json-data/sm-json-data) and covers a wide range of techniques, from casual play to
extremely difficult tricks.

This Archipelago world runs the actual Map Rando randomizer (version 123), so the game plays exactly like a seed from
maprando.com, except that items can come from, and go to, other worlds of the multiworld.

## What does randomization do to this game?

Map Rando generates a map layout and places items using its own logic, for the chosen skill assumptions. The
Archipelago logic is derived from Map Rando's item placement: Map Rando places items in "steps", and items from one
step's locations are only expected after all items from the previous steps have been obtained. Archipelago then
shuffles the items into the multiworld following this logic.

## Which settings are available?

All settings of the maprando.com "Generate" page, with the same presets:

- **Settings preset**: Default, Community Race Season 5, Mentor Tournament, Summer Series Expert Challenge.
- **Category presets**: skill assumptions (Basic to Insane+, plus Implicit and Beyond), item progression (Normal,
  Tricky, Technical, Challenge, Desolate), quality of life (Off, Low, Default, High, Max), objectives (None, Bosses,
  Minibosses, Chozos, Pirates, Metroids, Random), doors (Blue, Ammo, Beam).
- **Every individual setting**: all skill assumption values, enabled/disabled tech and notable strats, item
  progression rate and style, item pool, starting items, key item priorities, filler items, pickup sizes, all quality of
  life settings (enhanced map, initial map reveal, map station activation, crash fixes, ...), objectives, map layout
  (Vanilla, Small, Standard, Wild), area assignment, door counts per color, start location (including a custom start
  location), save the animals, collectible wall jump, split speed booster, savestates, and more.
- **Settings JSON**: settings saved on maprando.com can be pasted as `map_rando_settings`.

All cosmetic settings of the website's "Customize" page are available too: Samus sprite, energy tank color, room
theming (palettes and Mosaic tile themes), door colors, music, screen shaking and flashing, HUD and map appearance, and
controller layout (including spin lock, quick reload and savestate button combinations).

The way presets work is the same as on the website: choose a settings preset and category presets, then change
individual settings. Each individual setting defaults to `preset`, which keeps the preset's value.

## What items and locations get shuffled?

All 100 item locations are shuffled, with all of Map Rando's items: Energy Tanks, Reserve Tanks, Missiles, Super
Missiles, Power Bombs, beams, suits, boots and Morph Ball upgrades, plus Wall Jump Boots (with collectible wall jump),
Spark Booster and Blue Booster (with split Speed Booster). With a reduced item pool, some locations hold nothing.

## Which items can be in another player's world?

Any item can be in another player's world.

## What does another world's item look like in Super Metroid Map Rando Upstream?

With `item_matching: metroid`, items from other Metroid games look like the closest Super Metroid item. Other items
look like an Archipelago item (with an arrow for progression items). On the map, other worlds' items are marked like
the corresponding kind of Map Rando item.

## When the player receives an item, what happens?

A message box shows the item and who sent it, and the item is given immediately.

## What is the goal?

Complete the objectives, defeat Mother Brain and escape, as in Map Rando.

## Notes

- Generation downloads Map Rando's map pools (about 2 MB per map batch, cached). Applying a patch downloads Map
  Rando's Mosaic tile patches the first time (8 MB, cached) and the chosen Samus sprite if it isn't the default one.
- Several Map Rando worlds of a multiworld can share a map layout (`common_map`), and optionally their door colors
  (`common_door_colors`), with different start locations (`unique_start_locations`).
