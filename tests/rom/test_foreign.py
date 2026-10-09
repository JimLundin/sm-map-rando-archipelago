"""Other worlds' items at our locations: Map Rando foreign items (docs/specs/foreign-items.md), on our ROM."""
import json
import tempfile
from pathlib import Path

import pytest

from conftest import CORE, ROOT, VANILLA, boot_to_gameplay
from core import mwpatch
from core.catalog import LOCATION_ID_BASE
from local_engine import local_engine
from core.mwplan import message
from core.sync import SendLocations, Snapshot, step

MORPH_BALL_ROOM_ITEM = 13          # an open item; Samus starts left of it and walks right to pick it up
OTHERS = {10: "Progression", 42: "Useful", 77: "Filler"}   # a shot block, a shot block, a chozo orb
EQUIPMENT, BEAMS, MAX_MISSILES, MAX_ENERGY = 0x09A4, 0x09A8, 0x09C8, 0x09C4
MESSAGE_BOX, FRAME_COUNTER = 0x1C1F, 0x05B6


@pytest.fixture(scope="module")
def foreign_rom(abi, catalog) -> bytes:
    if not VANILLA or not Path(CORE).exists():
        pytest.skip("needs SMMR_TEST_ROM and a libretro SNES core (SMMR_SNES_CORE)")
    engine = local_engine()
    settings = json.loads((ROOT / "fixtures/settings/default-vanilla.upgraded.json").read_text())
    randomization = json.loads((ROOT / "fixtures/seeds/default-vanilla-1.json").read_text())["randomization"]
    foreign = {**OTHERS, MORPH_BALL_ROOM_ITEM: "Progression"}
    randomization["item_placement"] = ["Nothing" if i in foreign else item
                                       for i, item in enumerate(randomization["item_placement"])]
    randomization["foreign_items"] = [{"location_idx": i, "class": c, "message": message("Alice", "Hookshot")}
                                      for i, c in foreign.items()]
    location = catalog.locations[MORPH_BALL_ROOM_ITEM]
    vanilla = Path(VANILLA).read_bytes()
    x, y = vanilla[location.plm_addr + 2], vanilla[location.plm_addr + 3]
    randomization["start_location"] = dict(randomization["start_location"], name="Test", room_id=location.room_id,
                                           node_id=location.node_id, door_load_node_id=1, x=x - 1.5, y=y + 0.5)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "mr.sfc"
        engine.rom(settings, randomization, Path(VANILLA), out)
        map_rando_rom = out.read_bytes()
    return mwpatch.apply(map_rando_rom, (ROOT / "world/smmr/data/mw.ips").read_bytes(), abi, catalog,
                         mwpatch.rom_name(abi, 1, 12345))


@pytest.fixture(scope="module")
def foreign_game(foreign_rom):
    from emu import Emulator
    emu = Emulator(foreign_rom, CORE)
    boot_to_gameplay(emu)
    yield emu
    emu.close()


def collected(game, rom, location) -> bool:
    bit = rom[location.plm_addr + 4] | rom[location.plm_addr + 5] << 8
    return bool(game.wram[0xD870 + (bit >> 3)] >> (bit & 7) & 1)


def test_foreign_items_are_not_collected_in_a_new_game(foreign_game, foreign_rom, catalog):
    for index in (*OTHERS, MORPH_BALL_ROOM_ITEM):
        assert not collected(foreign_game, foreign_rom, catalog.locations[index]), index


def test_picking_up_a_foreign_item_shows_its_message_gives_nothing_and_the_client_reports_it(foreign_game, foreign_rom,
                                                                                             abi, catalog):
    game = foreign_game
    before = [game.wram.u16(a) for a in (EQUIPMENT, BEAMS, MAX_MISSILES, MAX_ENERGY)]
    location = catalog.locations[MORPH_BALL_ROOM_ITEM]
    for _ in range(16):   # the start pose ignores input for a few seconds; then she walks into the item
        game.hold("right")
        game.run(20)
        game.hold()
        game.run(10)
        if collected(game, foreign_rom, location):
            break
    assert collected(game, foreign_rom, location)
    game.run(30)
    assert game.wram.u16(MESSAGE_BOX) == 0x30   # the message box is open: the frame counter stops
    frame = game.wram.u16(FRAME_COUNTER)
    game.run(30)
    assert game.wram.u16(FRAME_COUNTER) == frame
    for _ in range(10):                          # A closes it once its fanfare or sound is done
        game.press("a", frames=6, release=54)
        if game.wram.u16(FRAME_COUNTER) != frame:
            break
    frame = game.wram.u16(FRAME_COUNTER)
    game.run(60)
    assert game.wram.u16(FRAME_COUNTER) == (frame + 60) & 0xFFFF
    assert [game.wram.u16(a) for a in (EQUIPMENT, BEAMS, MAX_MISSILES, MAX_ENERGY)] == before
    w = abi.wram
    table_start = mwpatch.snes_to_pc(abi.rom["location_table"])
    snapshot = Snapshot(game.wram.u16(w["game_state"]),
                        game.wram[w["collected_items"]:w["collected_items"] + w["collected_items_size"]],
                        game.wram.u16(w["received_count"]))
    actions = step(abi, foreign_rom[table_start:table_start + w["collected_items_size"] * 8], snapshot, set(), [])
    assert actions == [SendLocations((LOCATION_ID_BASE + MORPH_BALL_ROOM_ITEM,))]

