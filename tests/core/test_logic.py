from collections import Counter

from core.logic import FILLER, PROGRESSION, build_logic


def test_catalog_names_are_unique(catalog):
    assert len({loc.name for loc in catalog.locations}) == len(catalog.locations) == 100
    assert len({item.name for item in catalog.items}) == len(catalog.items)


def test_every_location_is_in_exactly_one_step(catalog, seed):
    logic = build_logic(seed, catalog)
    indexes = [i for step in logic.steps for i in step.locations] + list(logic.remaining.locations)
    assert sorted(indexes) == list(range(100))


def test_a_step_requires_exactly_the_items_of_earlier_steps(catalog, seed):
    logic = build_logic(seed, catalog)
    assert logic.steps[0].requires == {}
    collected = Counter()
    for step in logic.steps:
        assert step.requires == collected
        for index in step.locations:
            item = logic.pool[index]
            if item.name != "Nothing":
                collected[item.name] += 1
    assert logic.remaining.requires == collected


def test_pool_is_map_randos_placement(catalog, seed):
    logic = build_logic(seed, catalog)
    placement = seed["randomization"]["item_placement"]
    assert [item.name for item in logic.pool] == [catalog.item(name).name for name in placement]
    assert all(item.classification == PROGRESSION for item in logic.pool if item.step <= len(logic.steps))


def test_stop_early_leaves_the_rest_as_filler(catalog, seed):
    truncated = {**seed, "spoiler": {**seed["spoiler"], "summary": seed["spoiler"]["summary"][:3]}}
    logic = build_logic(truncated, catalog)
    assert len(logic.steps) == 3
    for index in logic.remaining.locations:
        assert logic.pool[index].classification == FILLER
