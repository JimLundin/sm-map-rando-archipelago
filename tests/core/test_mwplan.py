from core.catalog import Catalog
from core.logic import Classification
from core.mwplan import MESSAGE_ROW, OtherWorldItem, OwnItem, PlacedItem, message, message_text, plan


def test_other_worlds_items_are_nothing_and_foreign_items_with_their_class(catalog: Catalog) -> None:
    placed: list[PlacedItem] = [OwnItem("Missile")] * len(catalog.locations)
    placed[3] = OtherWorldItem("Varia Suit", "Alice", Classification.PROGRESSION)    # our game, another player
    placed[4] = OtherWorldItem("Arrows", "Alice", Classification.PROGRESSION_SKIP_BALANCING)
    placed[5] = OtherWorldItem("Hookshot", "Alice", Classification.USEFUL)
    placed[8] = OtherWorldItem("Rupee", "Bob", Classification.FILLER)
    mw = plan(catalog, placed)
    assert [mw.item_placement[i] for i in (0, 3, 4, 5, 8)] == ["Missile", "Nothing", "Nothing", "Nothing", "Nothing"]
    assert mw.foreign_items == [{"location_idx": 3, "class": "Progression", "message": ["ALICE - VARIA SUIT"]},
                                {"location_idx": 4, "class": "Progression", "message": ["ALICE - ARROWS"]},
                                {"location_idx": 5, "class": "Useful", "message": ["ALICE - HOOKSHOT"]},
                                {"location_idx": 8, "class": "Filler", "message": ["BOB - RUPEE"]}]


def test_a_solo_seed_has_no_foreign_items(catalog: Catalog) -> None:
    assert plan(catalog, [OwnItem("Missile")] * len(catalog.locations)).foreign_items == []


def test_message_text_is_what_the_font_can_show() -> None:
    assert message_text("Link's Bow (+1)") == "LINKS BOW 1"
    assert message_text("Zoë_42") == "ZOE 42"
    assert message_text("What?! Done.") == "WHAT?! DONE."


def test_a_long_message_puts_the_recipient_and_the_item_in_a_row_each() -> None:
    assert message("Alice", "Progressive Sword") == ["ALICE - PROGRESSIVE SWORD"]
    rows = message("A very long player name", "Small Key (Thieves' Town)")
    assert rows == ["A VERY LONG PLAYER NAME", "SMALL KEY THIEVES TOWN"]
    assert all(len(row) <= MESSAGE_ROW for row in message("x" * 40, "y" * 40))
