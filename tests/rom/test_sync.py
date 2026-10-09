"""The client's decisions (`core.sync`) against the real ROM: the emulator stands in for SNI."""
from core.abi import snes_to_pc
from core.catalog import ITEM_ID_BASE, LOCATION_ID_BASE
from core.mwpatch import location_bits
from core.sync import Action, Deliver, Received, SendLocations, Snapshot, step

VARIA, CHARGE = 12, 5


def snapshot(game, abi):
    w = abi.wram
    return Snapshot(game.wram.u16(w["game_state"]),
                    game.wram[w["collected_items"]:w["collected_items"] + w["collected_items_size"]],
                    game.wram.u16(w["received_count"]))


def rom_table(rom, abi):
    start = snes_to_pc(abi.rom["location_table"])
    return rom[start:start + abi.wram["collected_items_size"] * 8]


def poll(game, abi, table, checked, received) -> list[Action]:
    """One client poll: the emulator stands in for SNI."""
    actions = step(abi, table, snapshot(game, abi), checked, received)
    for action in actions:
        match action:
            case Deliver(seq, words):
                game.wram.write(abi.wram["mailbox_item"], words)
                game.wram.write_u16(abi.wram["mailbox_seq"], seq)
            case _:
                pass
    return actions


def sent(actions: list[Action]) -> list[int]:
    """The location ids the actions send."""
    return [location_id for action in actions if isinstance(action, SendLocations) for location_id in action.location_ids]


def test_the_client_delivers_received_items_in_order(game, abi, patched_rom):
    table = rom_table(patched_rom, abi)
    received = [Received(ITEM_ID_BASE + VARIA, 2), Received(ITEM_ID_BASE + CHARGE, 3)]
    for _ in range(40):   # a poll every 30 frames, closing message boxes
        poll(game, abi, table, set(), received)
        game.run(30)
        game.press("a")
    assert game.wram.u16(abi.wram["received_count"]) == 2
    assert game.wram.u16(0x09A4) & 0x0001 and game.wram.u16(0x09A8) & 0x1000


def test_a_collected_location_is_reported_once(game, abi, patched_rom, catalog):
    table = rom_table(patched_rom, abi)
    location = catalog.locations[42]
    bit = location_bits(patched_rom, catalog)[42]
    w = abi.wram
    game.wram[w["collected_items"] + (bit >> 3)] |= 1 << (bit & 7)   # as the item PLM's pickup does
    actions = poll(game, abi, table, set(), [])
    assert sent(actions) == [LOCATION_ID_BASE + location.index]
    assert sent(poll(game, abi, table, set(sent(actions)), [])) == []


def test_rom_identifies_itself(patched_rom, abi):
    start = snes_to_pc(abi.rom["rom_name"])
    assert patched_rom[start:start + 4] == b"SMMR"
    header = snes_to_pc(abi.rom["header"])
    assert patched_rom[header:header + 2] == abi.header()
