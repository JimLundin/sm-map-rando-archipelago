# Super Metroid Map Rando for Archipelago

An Archipelago world for [Super Metroid Map Rando](https://maprando.com) (Map Rando v123), rebuilt from the ground up.
It contains no code from lordlou's Map Rando world, lordlou's native binding or SMBasepatch (see
`docs/adr/0001-clean-room-rewrite.md`). It uses [Map Rando](https://github.com/blkerby/MapRandomizer) through our fork
([JimLundin/MapRandomizer](https://github.com/JimLundin/MapRandomizer), branch `foreign-item`): upstream plus
foreign items, which show other worlds' items (`docs/specs/foreign-items.md`).

You need your own Super Metroid (JU) ROM; none is included or distributed.

## How it works

See `docs/architecture.md` for the diagram. In short:

- **Engine** (`engine/`): `smmr_engine`, our Python module in Rust (PyO3, built by maturin) over the `MapRandomizer`
  submodule: our fork of Map Rando, upstream plus foreign items (ADR 0005). `Engine.world` (everything but the item
  placement), `Engine.open` and `Session.reach` (Map Rando's logic per inventory, ADR 0006), `Engine.rom`,
  `Engine.randomize` (Map Rando's own placement); its types are in `smmr_engine.pyi`.
- **Core** (`world/smmr/core/`): the pipeline stages as pure functions with JSON artifacts between them (options →
  settings → Seed → logic → plan → ROM). Standard library only.
- **World** (`world/smmr/`): thin Archipelago adapters. The World, the options (built from Map Rando's presets), the
  patch procedure and the SNI client.
- **Multiworld patch** (`mw/mw.asm`, ~300 bytes of our own asm): receiving items. Sending needs no asm (ADR 0003).
  All ROM addresses are in `world/smmr/data/abi.toml`.

## Development

Requirements: [uv](https://docs.astral.sh/uv/), Rust, a C++ compiler (for asar), a libretro SNES core for the ROM
tests (e.g. snes9x; `SMMR_SNES_CORE`), an Archipelago checkout for the World tests. uv provides Python 3.12 (what
Archipelago's installer bundles) and the dev tools (pytest, pyright, maturin, CMake), and builds the engine module
into `.venv`.

```
git clone --recursive … && cd …
uv sync                              # Python 3.12, dev tools, and the engine module
uv run tools/fetch_data.py           # Mosaic tile patches (Map Rando data not in its repository)
uv run tools/dev.py asar             # the assembler; then `uv run tools/dev.py mw` after asm changes
uv run tools/dev.py data             # world/smmr/data from the engine (commit the result)
```

`uv run` rebuilds the engine module first whenever its Rust (or Map Rando's) changed. The loops, fastest first:

| | |
|---|---|
| `uv run pytest tests/core` | core stages against recorded fixtures, ~0.1 s |
| `uv run tools/dev.py typecheck --ap ~/Archipelago` | pyright (`pyproject.toml`): strict for the core, its tests and the tools |
| `uv run tools/stage.py randomize settings.json --seed 1 -o seed.json` | run one stage from files |
| `uv run pytest tests/engine` | settings and the logic through the real engine, ~5 s |
| `SMMR_TEST_ROM=vanilla.sfc uv run pytest tests/rom` | our asm in a headless emulator, ~15 s |
| `uv run tools/dev.py test-ap --ap ~/Archipelago` | generation, fill and multiworld in Archipelago (symlinks `worlds/smmr`) |
| `uv run tools/dev.py e2e --ap … --rom …` | the packaged .apworld: generate, patch, boot (an Archipelago without `worlds/smmr`) |

`--ap` and `--rom` default to `SMMR_AP` and `SMMR_TEST_ROM`. After a Map Rando update (submodule bump):
`uv run tools/dev.py data` and `fixtures`, then the loops above.

## Release

`uv run tools/dev.py apworld` builds `dist/smmr.apworld` with this platform's engine module (`maturin build
--release`). For other platforms, pass their wheels: `uv run tools/build_apworld.py --engine linux-x86_64=… --engine
win32-amd64=…`. The world version is in `world/smmr/archipelago.json`.

## Status

Working: solo and multiworld generation, ROM patching, sending and receiving items (other worlds' items show who gets
them), the SNI client, options from Map Rando's presets, map pools downloaded on demand, packaging. Not yet:
customization, "from player X" on received items, shared maps, death link, hints,
credits, multi-platform CI (see `docs/architecture.md`).

## License and credits

- [Map Rando](https://github.com/blkerby/MapRandomizer) by blkerby (kyleb), maddo and contributors (MIT).
- [sm-json-data](https://github.com/vg-json-data/sm-json-data) (CC BY 4.0), the logic data Map Rando uses.
- Vanilla routine and RAM documentation from [patrickjohnston.org](https://patrickjohnston.org/bank/).
- [Archipelago](https://github.com/ArchipelagoMW/Archipelago) (MIT).

`LICENSE` is unchanged from the previous implementation (GPL-3.0). This rewrite no longer derives from GPL code, so
the license is the maintainer's choice.

Super Metroid is a trademark of Nintendo. This project is not affiliated with Nintendo or with maprando.com.
