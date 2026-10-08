# Super Metroid Map Rando for Archipelago

An Archipelago world for [Super Metroid Map Rando](https://maprando.com) (Map Rando v123), rebuilt from the ground up.
It contains no code from lordlou's Map Rando world, lordlou's native binding or SMBasepatch (see
`docs/adr/0001-clean-room-rewrite.md`). It uses [Map Rando](https://github.com/blkerby/MapRandomizer) through our fork
([JimLundin/MapRandomizer](https://github.com/JimLundin/MapRandomizer), branch `foreign-item`): upstream plus
foreign items, which show other worlds' items (`docs/specs/foreign-items.md`).

You need your own Super Metroid (JU) ROM; none is included or distributed.

## How it works

See `docs/architecture.md` for the diagram. In short:

- **Engine** (`engine/`): our Rust binary over the `MapRandomizer` submodule: our fork of Map Rando, upstream plus
  foreign items (ADR 0005). It speaks JSON: `info`, `upgrade`, `randomize`, `rom`, and `serve` for many requests from
  one process.
- **Core** (`world/smmr/core/`): the pipeline stages as pure functions with JSON artifacts between them (options →
  settings → Seed → logic → plan → ROM). Standard library only.
- **World** (`world/smmr/`): thin Archipelago adapters. The World, the options (built from Map Rando's presets), the
  patch procedure and the SNI client.
- **Multiworld patch** (`mw/mw.asm`, ~300 bytes of our own asm): receiving items. Sending needs no asm (ADR 0003).
  All ROM addresses are in `world/smmr/data/abi.toml`.

## Development

Requirements: Rust, Python 3.11+, CMake and a C++ compiler (for asar), a libretro SNES core for the ROM tests (e.g.
snes9x; `SMMR_SNES_CORE`), an Archipelago checkout for the World tests.

```
git clone --recursive … && cd …
make fetch            # Mosaic tile patches (Map Rando data not in its repository)
make engine asar mw   # engine (incremental, optimized), assembler, multiworld patch
make data             # world/smmr/data from the engine (commit the result)
```

The loops, fastest first:

| | |
|---|---|
| `make test-core` | core stages against recorded fixtures, ~0.1 s |
| `python tools/stage.py randomize settings.json --seed 1 -o seed.json` | run one stage from files |
| `pytest tests/engine` | settings through the real engine, ~2 s |
| `make test-rom ROM=vanilla.sfc` | our asm in a headless emulator, ~3 s |
| `make test-ap AP=~/Archipelago` | generation, fill and multiworld in Archipelago (symlinks `worlds/smmr`) |
| `make e2e AP_CLEAN=… ROM=…` | the packaged .apworld: generate, patch, boot to gameplay |

After a Map Rando update (submodule bump): `make data fixtures`, then the loops above.

## Release

`make apworld` builds `dist/smmr.apworld` with this platform's engine. For other platforms, pass their builds:
`python tools/build_apworld.py --engine linux-x86_64=… --engine win32-amd64=…`. The world version is in
`world/smmr/archipelago.json`.

## Status

Working: solo and multiworld generation, ROM patching, sending and receiving items (other worlds' items show who gets
them), the SNI client, options from Map Rando's presets, map pools downloaded on demand, packaging. Not yet:
customization, per-class off-world item graphics, "from player X" on received items, shared maps, death link, hints,
credits, multi-platform CI (see `docs/architecture.md`).

## License and credits

- [Map Rando](https://github.com/blkerby/MapRandomizer) by blkerby (kyleb), maddo and contributors (MIT).
- [sm-json-data](https://github.com/vg-json-data/sm-json-data) (CC BY 4.0), the logic data Map Rando uses.
- Vanilla routine and RAM documentation from [patrickjohnston.org](https://patrickjohnston.org/bank/).
- [Archipelago](https://github.com/ArchipelagoMW/Archipelago) (MIT).

`LICENSE` is unchanged from the previous implementation (GPL-3.0). This rewrite no longer derives from GPL code, so
the license is the maintainer's choice.

Super Metroid is a trademark of Nintendo. This project is not affiliated with Nintendo or with maprando.com.
