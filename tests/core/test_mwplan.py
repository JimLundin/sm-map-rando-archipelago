from core.logic import FILLER, PROGRESSION, USEFUL
from core.mwplan import MESSAGE_ROW, PlacedItem, message, message_text, plan

GAME = "Super Metroid Map Rando"


def test_other_worlds_items_are_nothing_and_foreign_items_with_their_class(catalog):
    placed = [PlacedItem("Missile", 1, GAME)] * len(catalog.locations)
    placed[3] = PlacedItem("Varia Suit", 2, GAME, PROGRESSION, "Alice")       # our game, another player
    placed[5] = PlacedItem("Hookshot", 2, "Other Game", USEFUL, "Alice")
    placed[8] = PlacedItem("Rupee", 3, "Other Game", FILLER, "Bob")
    mw = plan(catalog, placed, 1, GAME)
    assert [mw.item_placement[i] for i in (0, 3, 5, 8)] == ["Missile", "Nothing", "Nothing", "Nothing"]
    assert mw.foreign_items == [{"location_idx": 3, "class": "Progression", "message": ["ALICE - VARIA SUIT"]},
                                {"location_idx": 5, "class": "Useful", "message": ["ALICE - HOOKSHOT"]},
                                {"location_idx": 8, "class": "Filler", "message": ["BOB - RUPEE"]}]


def test_message_text_is_what_the_font_can_show():
    assert message_text("Link's Bow (+1)") == "LINKS BOW 1"
    assert message_text("Zoë_42") == "ZOE 42"
    assert message_text("What?! Done.") == "WHAT?! DONE."


def test_a_long_message_puts_the_recipient_and_the_item_in_a_row_each():
    assert message("Alice", "Progressive Sword") == ["ALICE - PROGRESSIVE SWORD"]
    rows = message("A very long player name", "Small Key (Thieves' Town)")
    assert rows == ["A VERY LONG PLAYER NAME", "SMALL KEY THIEVES TOWN"]
    assert all(len(row) <= MESSAGE_ROW for row in message("x" * 40, "y" * 40))


def test_a_solo_seed_has_no_foreign_items(catalog):
    placed = [PlacedItem("Missile", 1, GAME)] * len(catalog.locations)
    assert plan(catalog, placed, 1, GAME).foreign_items == []
