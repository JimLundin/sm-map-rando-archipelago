from core.logic import FILLER, PROGRESSION, USEFUL
from core.mwplan import PlacedItem, plan

GAME = "Super Metroid Map Rando"


def test_other_worlds_items_are_nothing_and_foreign_items_with_their_class(catalog):
    placed = [PlacedItem("Missile", 1, GAME)] * len(catalog.locations)
    placed[3] = PlacedItem("Varia Suit", 2, GAME, PROGRESSION)       # our game, another player
    placed[5] = PlacedItem("Hookshot", 2, "Other Game", USEFUL)
    placed[8] = PlacedItem("Rupee", 3, "Other Game", FILLER)
    mw = plan(catalog, placed, 1, GAME)
    assert [mw.item_placement[i] for i in (0, 3, 5, 8)] == ["Missile", "Nothing", "Nothing", "Nothing"]
    assert mw.foreign_items == [{"location_idx": 3, "class": "Progression"},
                                {"location_idx": 5, "class": "Useful"},
                                {"location_idx": 8, "class": "Filler"}]


def test_a_solo_seed_has_no_foreign_items(catalog):
    placed = [PlacedItem("Missile", 1, GAME)] * len(catalog.locations)
    assert plan(catalog, placed, 1, GAME).foreign_items == []
