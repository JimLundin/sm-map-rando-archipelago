# 0001: A clean-room rewrite

Status: accepted (2026-10)

## Context

The previous implementation grew out of lordlou's Map Rando world. It inherited that world's structure, the
`pysmmaprando` native binding, a patched copy of upstream Map Rando, and SMBasepatch (the multiworld ROM patch by
Thomas Backmark and lordlou). Its own architecture review found the same problems over and over: JSON-shaped
facts copied between Python, asm and tools; a seam to Rust that was only half there; logic that only a real ROM
could exercise.

## Decision

Start over in a new tree, using none of that code: not the world, not the binding, not SMBasepatch, and none of the
patches to upstream Map Rando. What we build on:

- upstream Map Rando (MIT), unmodified, plus its own asm patches as references for PLM patterns;
- the public Super Metroid disassembly documentation (patrickjohnston.org) for vanilla routines and RAM;
- Archipelago's public World, patch and SNI client APIs.

The new tree has no AP-SM or basepatch ROM ABI. Its ABI is our own (`world/smmr/data/abi.toml`), so its ROMs and
patch files aren't compatible with the previous releases' (the patch suffix is `.apsmmr`).

## Consequences

- The project no longer has to be GPL as a derivative of lordlou's world. Relicensing is a separate decision for
  the maintainer. `LICENSE` is unchanged for now.
- Features the previous world had and this one doesn't yet (customization, off-world item graphics, messages,
  shared maps, death link) have to be rebuilt. `docs/architecture.md` lists them.
