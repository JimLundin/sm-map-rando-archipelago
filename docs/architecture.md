# Architecture

The Super Metroid Map Rando world for Archipelago, rebuilt from the ground up. It has no code from lordlou's world,
lordlou's `pysmmaprando` binding or SMBasepatch (ADR 0001). Its upstream is Map Rando (blkerby/MapRandomizer, MIT),
used through our fork: upstream plus foreign items (ADR 0002, ADR 0005), plus Archipelago's public World and SNI
client APIs.

## Principles

1. **Stages with artifact boundaries.** Generation is a pipeline of stages. Each stage is a function from one
   serializable artifact to the next. Any artifact can be dumped to JSON, and any later stage re-run from it alone
   (`tools/stage.py`).
2. **Map Rando is a black box.** Our own engine binary calls the upstream crate the way Map Rando's website does.
   Our multiworld layer goes *on top of* the ROM Map Rando produces.
3. **One owner per fact.** The ROM ABI is `world/smmr/data/abi.toml` only: the asm defines and the Python codecs are
   generated from it. Item locations, preset names and map pools come from the engine's `info`.
4. **A pure core.** `world/smmr/core/` imports only the standard library (a test enforces this). The AP World, the
   patch procedure and the SNI client are thin adapters around core stages.
5. **A fast loop per layer.** Each layer has a seconds-long edit→test loop. Everything together runs before a
   release (`make e2e`).

## Diagram

```
 GENERATION (Archipelago, world/smmr/__init__.py)                                       artifacts
 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
  player YAML ─► options.py (data-driven Choices) ─► [S1 core.options] ──────────────────► settings (pre-upgrade)
                                                           │
                         ┌──────────────── engine port (core.engine) ───────────────┐
                         │  smmr-engine serve  (Rust, Map Rando: our fork)           │
                         │    upgrade · world · open · reach · rom · info  JSON lines │
                         └───────────────────────────────────────────────────────────┘
                                                           │ upgrade ─────────────────► RandoSettings
                                                           │ world ───────────────────► GeneratedWorld (map, doors,
                                                           │                             objectives, start; pool)
                                                           ▼
                                              [S3 core.logic] Oracle ◄── reach (session): Map Rando's traversal,
                                                           │              per inventory of our items, cached
                                              AP fill: every rule asks the Oracle
                                                           ▼
                                              [S4 core.mwplan] ───────────────────────► MwPlan (what each
                                                           │                             location shows)
                                                           ▼
                                              .apsmmr = smmr.json {settings, world, item_placement,
                                                                   foreign_items, rom_name}

 PATCHING (player's machine, patch.py)
 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
  vanilla ROM ─► [S5a engine rom] ─► Map Rando ROM ─► [S5b core.mwpatch] ─► ROM
                                                       mw.ips (our asm) + ABI header + bit→location table + name

 PLAY
 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
  ROM ◄── SNI ──► client.py ──► [S6 core.sync] ──► AP server
   │ collected-item bits $7E:D870   (send: any pickup sets them; others' items are foreign items)
   │ mailbox $7E:F5A0 ◄─ client      (receive: the tick spawns the item's own Map Rando PLM on Samus)
   │ received count $7E:FE94 ─► client (saved with the save file)

 SINGLE SOURCES
 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
  data/abi.toml ──► tools/build_mw.py ──► mw/build/abi.asm ──► mw/mw.asm ──► data/mw.ips
              └───► core/abi.py (patcher and client codecs)
  engine info ───► data/info.json (locations, items, category presets, map pools)
  Map Rando presets ─► data/presets.json ─► the options
```

## Layers and code ownership

```
 world/smmr/                    the .apworld package
   __init__.py                  AP World: hooks → core stages
   options.py                   AP options, built from Map Rando's presets when the world loads
   patch.py                     APProcedurePatch: S5a + S5b
   client.py                    SNI client: SNI I/O around core.sync
   runtime.py                   finds/extracts the engine and data; downloads map pools (fetch.py)
   core/                        pure, standard library only
     options.py   S1            option values → Map Rando settings
     engine.py    port          Engine protocol + SubprocessEngine (one `serve` process)
     catalog.py                 items and item locations, names and ids
     logic.py     S3            the Oracle (rules from Map Rando's traversal); the item pool
     mwplan.py    S4            AP placement → Map Rando item placement
     mwpatch.py   S5b           Map Rando ROM → multiworld ROM
     abi.py, ips.py             ROM ABI codecs, IPS
     sync.py      S6            memory snapshot → client actions
   data/                        abi.toml, mw.ips, info.json, presets.json (generated, committed)
 engine/                        Rust: smmr-engine (path dependency on MapRandomizer/, our fork)
 mw/                            our 65816 asm (asar)
 tools/                         stage runner, builds, emulator harness, fixture recording, e2e
 tests/core  tests/engine  tests/rom      per-layer tests; world/smmr/test runs inside Archipelago
```

## Iteration loops

| Layer | Feedback | Command |
|---|---|---|
| core stages | ~0.1 s, no AP, no Rust: recorded Seed fixture | `make test-core` |
| engine | incremental build; any stage from JSON files; engine tests ~2 s | `make engine`, `tools/stage.py …`, `pytest tests/engine` |
| mw asm | assemble < 1 s; ROM scenarios in a headless emulator ~3 s | `make mw test-rom ROM=…` |
| AP World | generation, fill, multiworld in an Archipelago checkout ~45 s | `make test-ap` |
| full | build the .apworld, generate, patch, boot | `make e2e ROM=…` |

## Decisions

- [ADR 0001](adr/0001-clean-room-rewrite.md): a clean-room rewrite, with no code from lordlou's world, binding or
  basepatch.
- [ADR 0002](adr/0002-engine-subprocess.md): the engine is our own binary over Map Rando, behind JSON.
- [ADR 0003](adr/0003-multiworld-on-map-rando-plms.md): send through Nothing items (superseded by 0005), receive by
  spawning the item's own PLM.
- [ADR 0004](adr/0004-step-logic.md): logic from Map Rando's placement steps (superseded by 0006).
- [ADR 0005](adr/0005-foreign-items-in-our-map-rando-fork.md): other worlds' items are foreign items, in our fork
  of Map Rando.
- [ADR 0006](adr/0006-logic-from-map-randos-traversal.md): logic from Map Rando's own traversal, asked from scratch
  per inventory.

## Not done yet

- Customization (sprite, palettes, music, controller): the ROM uses Map Rando's defaults.
- Received items show only their own message box, without who sent them.
- Shared maps across worlds, death link, hint area data and item credits.
- Engine builds for platforms other than this machine's (CI matrix), and release automation.
