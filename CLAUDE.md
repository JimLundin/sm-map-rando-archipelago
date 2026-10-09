## Agent skills

### Issue tracker

Issues are local markdown files under `.scratch/<feature>/`; specs live in `docs/specs/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage roles, recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: the glossary is `CONTEXT.md` at the root, and ADRs go in `docs/adr/`. See `docs/agents/domain.md`.

## Python style

Python 3.11, the oldest Archipelago supports (`ModuleUpdate.py`: 3.11 to 3.13): no `type X = ...`, no `class C[T]`,
no `@override`. Model variants as discriminated unions: frozen, slotted dataclasses joined in a `TypeAlias`, handled
with `match` and closed by `assert_never`. Builtin generics, `X | None`, ABCs from `collections.abc`, `StrEnum`,
`Self`. Parse JSON into typed values at the engine port. `make typecheck` (pyright, configured in `pyproject.toml`) is
strict for `world/smmr/core`, `tests/core` and `tools`.
