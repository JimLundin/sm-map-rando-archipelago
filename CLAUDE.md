## Agent skills

### Issue tracker

Issues are local markdown files under `.scratch/<feature>/`; specs live in `docs/specs/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage roles, recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: the glossary is `CONTEXT.md` at the root, and ADRs go in `docs/adr/`. See `docs/agents/domain.md`.

## Python style

Python 3.12, what Archipelago's installer bundles (and the target on Windows): `type X = ...` aliases, PEP 695
generics, `@override` on methods of Archipelago's classes. Model variants as discriminated unions: frozen, slotted
dataclasses joined in a `type` alias, handled with `match` and closed by `assert_never`. Builtin generics, `X | None`,
ABCs from `collections.abc`, `StrEnum`, `Self`. Parse JSON into typed values at the engine port. Tooling is uv (no make):
`uv run tools/dev.py typecheck --ap <Archipelago checkout>` (pyright, configured in `pyproject.toml`) is strict for
`world/smmr/core`, `tests/core` and `tools`, and checks the World's adapters against Archipelago.
