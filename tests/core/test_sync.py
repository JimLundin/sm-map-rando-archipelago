from test_abi import ABI

from core.catalog import ITEM_ID_BASE, LOCATION_ID_BASE
from core.sync import GAMEPLAY, Received, Snapshot, step

TABLE = ABI.location_table([3, 9])
NO_BITS = bytes(ABI.wram["collected_items_size"])


def bits(*set_bits):
    out = bytearray(NO_BITS)
    for bit in set_bits:
        out[bit >> 3] |= 1 << (bit & 7)
    return bytes(out)


def test_new_locations_only():
    actions = step(ABI, TABLE, Snapshot(GAMEPLAY, bits(3, 9), 0), {LOCATION_ID_BASE + 0}, [])
    assert actions.new_locations == [LOCATION_ID_BASE + 1]


def test_mailbox_holds_the_item_after_the_received_count():
    received = [Received(ITEM_ID_BASE + 12, 2), Received(ITEM_ID_BASE + 5, 3)]
    assert step(ABI, TABLE, Snapshot(GAMEPLAY, NO_BITS, 1), set(), received).mailbox == (2, bytes([5, 0, 3, 0]))
    assert step(ABI, TABLE, Snapshot(GAMEPLAY, NO_BITS, 2), set(), received).mailbox is None


def test_an_item_the_rom_cant_give_still_takes_its_number():
    received = [Received(ITEM_ID_BASE + ABI.items["nothing"], 2)]
    seq, words = step(ABI, TABLE, Snapshot(GAMEPLAY, NO_BITS, 0), set(), received).mailbox
    assert seq == 1 and int.from_bytes(words[:2], "little") >= ABI.items["count"]


def test_nothing_happens_outside_gameplay_except_finishing():
    received = [Received(ITEM_ID_BASE + 12, 2)]
    title = step(ABI, TABLE, Snapshot(0x01, bits(3), 0), set(), received)
    assert not title.new_locations and title.mailbox is None and not title.finished
    assert step(ABI, TABLE, Snapshot(0x26, NO_BITS, 0), set(), []).finished
