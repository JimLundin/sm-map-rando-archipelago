# 0002: The engine is our binary over unmodified Map Rando, behind JSON

Status: accepted (2026-10)

## Context

Map Rando is a Rust workspace. Its website and CLI call the `maprando` crate directly: load `GameData` from paths
relative to `rust/`, randomize, `make_rom`. A Python extension module (pyo3) would mean one wheel per Python ABI
and platform, a binding that must chdir or have its paths patched, and crashes that take the generator down.

## Decision

`engine/` is a small Rust binary, `smmr-engine`, with a path dependency on the `MapRandomizer` submodule, which is
pinned and not patched. It copies the website's randomization loop (`handle_randomize_request`) and speaks JSON:

- `info`, `upgrade`, `randomize` and `rom`, one-shot with a request on stdin, for tools and debugging;
- `serve`, one request per line, so a generation loads Map Rando's data once.

Map Rando prints progress to stdout, so responses are lines starting with the byte 1E. Because the engine is its own
process, it changes directory to `<data>/rust` freely.

The world talks to it only through `core.engine.Engine` (the port). Releases bundle one binary per platform
plus a zip of the Map Rando data the engine reads; the world extracts them to Archipelago's cache, into a directory
named by their hash.

## Consequences

- No upstream patches to keep applying, and an upstream update is a submodule bump plus `make data fixtures`.
- No Python ABI coupling: one binary per OS/architecture.
- An engine crash surfaces as an error with its stderr, not a dead generator.
- Facts the world needs from Map Rando (item locations and their PLM addresses, category preset names, map pools)
  come from `info`, recorded in `world/smmr/data/info.json`.
