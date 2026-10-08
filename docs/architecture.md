# Architecture (rewrite)

A ground-up rewrite of the Super Metroid Map Rando Archipelago world. It contains no code from lordlou's
world, lordlou's `pysmmaprando` binding, or SMBasepatch. Its only upstream is Map Rando (blkerby/MapRandomizer,
MIT), used **unmodified**, plus Archipelago's public World/SNI APIs.

## Principles

1. **Stages with file boundaries.** Generation is a pipeline of stages. Each stage is a function from one
   serializable artifact to the next. Any artifact can be dumped to JSON, and any later stage can be re-run
   from it alone.
2. **Map Rando is a black box.** We call the upstream crate the way its own CLI does, from our own binary.
   We don't patch it. Our multiworld layer is applied *on top of* the ROM Map Rando produces.
3. **One owner per fact.** The ROM ABI (addresses, table formats, item ids) is written once, in `mw/abi.toml`.
   It is generated into asm defines and a Python module.
4. **A pure core.** `core/` doesn't import Archipelago, the engine, or a ROM. The AP World is a thin adapter.
5. **A fast loop per layer.** Each layer has its own seconds-long edit→test loop. The slow, everything-together
   test only runs before a release.

## Diagram

```
                         ┌──────────────────────── Archipelago (generation) ────────────────────────┐
                         │                                                                           │
  player YAML ──► [S1] options ──► RandoSettings.json                                                │
                         │              │                                                             │
                         │              ▼                                                             │
                         │   ┌─────────────────────┐   subprocess, JSON stdin/stdout                  │
                         │   │ [S2] engine          │◄──────────────────────────────┐                 │
                         │   │  `smmr-engine        │                               │                 │
                         │   │   randomize`         │──► Seed.json                  │                 │
                         │   └─────────────────────┘   (map, doors, objectives,    │                 │
                         │                              placement, spoiler steps)  │                 │
                         │              │                                           │                 │
                         │              ▼                                           │                 │
                         │   [S3] logic: Seed ──► LogicModel (regions, step reqs)    │                 │
                         │              │                                           │                 │
                         │              ▼                                           │                 │
                         │   AP fill (multiworld) ──► Placement (per location:      │                 │
                         │              │               item, receiver, class)      │                 │
                         │              ▼                                           │                 │
                         │   [S4] mwplan: Seed + Placement ──► MwPlan               │                 │
                         │              │     (vanilla-item placement for map icons,│                 │
                         │              │      per-location table rows, players)    │                 │
                         │              ▼                                           │                 │
                         │   .apsmmr patch = { RandoSettings, Seed, MwPlan, rom_name }                 │
                         └──────────────┼───────────────────────────────────────────┼─────────────────┘
                                        │                                           │
                         ┌──────────────▼─────────── Patching (player's machine) ───┼─────────────────┐
                         │   [S5a] `smmr-engine rom`: vanilla ROM + Seed ──► MR ROM ┘                 │
                         │   [S5b] mw: MR ROM + mw.ips + encode(MwPlan) ──► final ROM                  │
                         │          (rewrites the 100 item PLMs to our MW PLMs)                        │
                         └──────────────┬─────────────────────────────────────────────────────────────┘
                                        │ SNES (emulator / hardware)
                         ┌──────────────▼──────────── Play ───────────────────────────────────────────┐
                         │   ROM  ◄── SNI ──►  [S6] client (core.abi codecs) ◄──► AP server            │
                         │   writes: collected-location bits    reads: receive queue head/tail        │
                         └────────────────────────────────────────────────────────────────────────────┘

  Single source of the ROM ABI:
        mw/abi.toml ──gen──► mw/build/abi.asm  (asar defines)
                    └─gen──► world/smmr/core/abi_gen.py (addresses, struct layouts, codecs use it)
```

### Layers and code ownership

```
 ┌────────────────────────────────────────────────────────────────────────────┐
 │ world/smmr/            the .apworld package                                  │
 │   __init__.py, world.py   AP adapter: AP hooks → core stages (thin)          │
 │   client.py               SNI adapter: SNI I/O → core.abi codecs (thin)      │
 │   patch.py                APProcedurePatch: runs S5a + S5b                   │
 │   core/   (pure, no AP / no I/O except via ports)                             │
 │     options.py   S1   options values → RandoSettings                          │
 │     logic.py     S3   Seed → LogicModel                                       │
 │     mwplan.py    S4   Seed + Placement → MwPlan                               │
 │     abi.py       ABI codecs (tables, queue entries, location bits)            │
 │     engine.py    Engine port: randomize(), rom()  + SubprocessEngine          │
 │     model.py     dataclasses for the artifacts (to/from JSON)                 │
 ├────────────────────────────────────────────────────────────────────────────┤
 │ engine/        Rust bin `smmr-engine` (path dep on MapRandomizer, unmodified)│
 │   randomize: RandoSettings + seed → Seed       rom: ROM + Seed → MR ROM      │
 │   info: item/location/preset tables (to generate options and fixtures)       │
 ├────────────────────────────────────────────────────────────────────────────┤
 │ mw/            our own 65816 multiworld patch (asar) + abi.toml              │
 ├────────────────────────────────────────────────────────────────────────────┤
 │ tools/         build (Makefile targets), fixture recorder, emulator harness  │
 └────────────────────────────────────────────────────────────────────────────┘
```

## Iteration loops

| Layer | Edit → feedback | Command |
|---|---|---|
| core stages | < 2 s, no AP, no Rust: recorded `Seed` fixtures | `make test-core` |
| engine | incremental `cargo build`, then run one stage from a JSON file | `make engine && tools/run-stage randomize fixtures/settings/basic.json` |
| mw asm | assemble < 1 s; emulator scenario tests with a ROM | `make mw && make test-mw` |
| AP World | symlink into an Archipelago checkout, generation tests | `make test-ap` |
| full | build the .apworld; generate, patch and boot in the emulator | `make e2e` (before a release) |

## Milestones (each one a short, mergeable vertical slice)

1. **Skeleton**: layout, Makefile, the core import guard, artifact dataclasses, docs/ADRs.
2. **Engine `randomize` + `rom`**: settings → Seed → ROM from the CLI. Record fixtures.
3. **Solo world, Map Rando items**: S1 (fixed preset), S3, AP generation, patch = engine `rom` only.
   It's playable as a 1-player AP seed, with no client yet.
4. **MW ABI + patch, own items**: abi.toml, the PLM rewrite, per-location table, pickup → collected bits.
   The emulator test picks up an item.
5. **Off-world items + client**: send/receive queue, message boxes, player names, SNI client.
6. **Options**: generated from Map Rando's settings schema and presets (via `engine info`).
7. **Extras**: shared maps, death link, hints, credits, CI release.
