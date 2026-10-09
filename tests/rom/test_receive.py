"""Receiving items: the client's mailbox → the item's own pickup in game."""
import pytest

VARIA, MISSILE, ETANK, CHARGE, HI_JUMP, NOTHING = 12, 1, 0, 5, 7, 22
EQUIPMENT_COLLECTED, BEAMS_COLLECTED, MAX_MISSILES, MAX_ENERGY = 0x09A4, 0x09A8, 0x09C8, 0x09C4


def post(game, abi, seq, item, sender=2):
    game.wram.write(abi.wram["mailbox_item"], abi.mailbox(item, sender) or item.to_bytes(2, "little") + b"\0\0")
    game.wram.write_u16(abi.wram["mailbox_seq"], seq)


def receive(game, abi, seq, item):
    """Post the item and play until it's given and its message box is closed."""
    post(game, abi, seq, item)
    for _ in range(600):
        game.run(1)
        if game.wram.u16(abi.wram["received_count"]) == seq:
            break
    game.run(240)
    game.press("a")
    game.run(60)


@pytest.mark.parametrize("item, address, expected", [
    (VARIA, EQUIPMENT_COLLECTED, 0x0001),
    (CHARGE, BEAMS_COLLECTED, 0x1000),
    (HI_JUMP, EQUIPMENT_COLLECTED, 0x0100),
])   # Wall Jump Boots and the split speed items exist only with their Map Rando settings, not in this seed
def test_received_upgrades_are_collected(game, abi, item, address, expected):
    receive(game, abi, 1, item)
    assert game.wram.u16(abi.wram["received_count"]) == 1
    assert game.wram.u16(address) & expected


def test_received_tanks_raise_capacity(game, abi):
    missiles, energy = game.wram.u16(MAX_MISSILES), game.wram.u16(MAX_ENERGY)
    receive(game, abi, 1, MISSILE)
    receive(game, abi, 2, ETANK)
    assert game.wram.u16(MAX_MISSILES) == missiles + 5
    assert game.wram.u16(MAX_ENERGY) == energy + 100
    assert game.wram.u16(abi.wram["received_count"]) == 2


def test_only_the_next_item_is_received(game, abi):
    post(game, abi, 2, VARIA)   # item 2 before item 1: wait
    game.run(120)
    assert game.wram.u16(abi.wram["received_count"]) == 0
    assert not game.wram.u16(EQUIPMENT_COLLECTED) & 0x0001


def test_items_the_rom_cant_give_are_skipped(game, abi):
    post(game, abi, 1, NOTHING)
    game.run(10)
    assert game.wram.u16(abi.wram["received_count"]) == 1
    post(game, abi, 2, 99)
    game.run(10)
    assert game.wram.u16(abi.wram["received_count"]) == 2


def test_receiving_sets_no_location_bit(game, abi):
    before = game.wram[abi.wram["collected_items"]:abi.wram["collected_items"] + abi.wram["collected_items_size"]]
    receive(game, abi, 1, VARIA)
    after = game.wram[abi.wram["collected_items"]:abi.wram["collected_items"] + abi.wram["collected_items_size"]]
    assert after == before
