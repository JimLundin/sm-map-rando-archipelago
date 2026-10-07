# 02: Generation covers `generate_output`

**Spec:** docs/specs/rom-item-plan.md

**What to build:** one generation test in `test_generation.py` that runs `generate_output` into a temporary directory
and checks a patch is produced, so the World's output path (today `get_item_placement_and_ap_data` and
`build_ap_data`; after ticket 03 the planner's input building) runs in CI. It is written against today's code, as a
safety net for ticket 03.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A generation test calls `generate_output` in a temporary directory and passes on today's code
- [ ] It runs where CI runs the other generation tests (no real ROM needed)
- [ ] It checks something meaningful about the output (for example, the `"ap"` block has one row per item location)
