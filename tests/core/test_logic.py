from collections.abc import Sequence

from core.catalog import Catalog
from core.logic import Classification, Inventory, Oracle, Reach, item_pool


def test_catalog_names_are_unique(catalog: Catalog) -> None:
    assert len({loc.name for loc in catalog.locations}) == len(catalog.locations) == 100
    assert len({item.name for item in catalog.items}) == len(catalog.items)


def test_the_logic_counts_every_item_but_nothing(catalog: Catalog) -> None:
    pool = {item.classification: item.name for item in item_pool({"Morph": 1, "Missile": 2, "Nothing": 1}, catalog)}
    assert pool == {Classification.PROGRESSION: "Morph Ball", Classification.PROGRESSION_SKIP_BALANCING: "Missile",
                    Classification.FILLER: "Nothing"}
    assert len(item_pool({"Missile": 46}, catalog)) == 46


def test_the_oracle_asks_once_per_inventory() -> None:
    asked: list[dict[str, int]] = []

    def query(inventories: Sequence[Inventory]) -> list[Reach]:
        asked.extend(dict(x) for x in inventories)
        return [Reach(frozenset(range(sum(x.values()))), "Morph" in x) for x in inventories]

    oracle = Oracle(query)
    assert oracle.reach({"Morph": 1, "Missile": 2}) == Reach(frozenset({0, 1, 2}), True)
    assert oracle.reach({"Missile": 2, "Morph": 1, "Bombs": 0}).beatable   # the same inventory
    assert oracle.reach({}) == Reach(frozenset(), False)
    assert asked == [{"Missile": 2, "Morph": 1}, {}]
    assert oracle.queries == 2
