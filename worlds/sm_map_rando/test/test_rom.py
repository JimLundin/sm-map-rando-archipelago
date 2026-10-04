"""
Tests of the Archipelago part of ROM patching (basepatch, item tables, item PLMs). The Map Rando patcher itself needs a
real Super Metroid ROM, so it is not exercised here: a synthetic ROM stands in for its output.
"""
import unittest

from ..Locations import LOCATIONS
from ..Rom import MAPRANDO_LOAD_HOOK, apply_archipelago, get_symbols, rom_item_name, snes_to_pc, write_checksum


def synthetic_roms():
    base = bytearray(0x300000)
    for i, loc in enumerate(LOCATIONS):
        container = i % 3  # visible, chozo, hidden
        plm = 0xEED7 + 84 * container + 4 * (i % 21)
        base[loc["plm_ptr"]:loc["plm_ptr"] + 2] = plm.to_bytes(2, "little")
    patched = bytearray(base) + bytearray(0x100000)
    addr, hook = MAPRANDO_LOAD_HOOK
    patched[snes_to_pc(addr):snes_to_pc(addr) + len(hook)] = hook
    return bytes(base), patched


class TestApplyArchipelago(unittest.TestCase):
    def test_tables_and_plms(self):
        base, rom = synthetic_roms()
        locations = []
        for i, loc in enumerate(LOCATIONS):
            if i == 0:
                locations.append([loc["bit_index"], 0, 22, False, "Nothing", 1])  # own Nothing
            elif i == 1:
                locations.append([loc["bit_index"], 1, None, True, "Hookshot", 2])  # off-world item
            elif i == 2:
                locations.append([loc["bit_index"], 1, 12, True, "Varia Suit", 3])  # another Map Rando world's item
            else:
                locations.append([loc["bit_index"], 0, 1, False, "Missile", 1])
        ap = {"player_ids": [0, 1, 2, 3], "player_names": ["Archipelago", "Me", "Link", "Samus"],
              "locations": locations, "own_player_id": 1, "death_link": 1, "remote_items": False}
        apply_archipelago(rom, base, ap, b"SMMR068_1_00000000042")
        write_checksum(rom)
        sym = get_symbols()

        def read(symbol, offset, n):
            a = snes_to_pc(sym[symbol]) + offset
            return bytes(rom[a:a + n])

        # item table rows: [destination type, item id, other player index, non-advancement]
        row = lambda bit: [int.from_bytes(read("rando_item_table", bit * 8 + 2 * k, 2), "little") for k in range(4)]
        self.assertEqual(row(LOCATIONS[1]["bit_index"]), [1, 25, 2, 0])
        self.assertEqual(row(LOCATIONS[2]["bit_index"]), [1, 12, 3, 0])
        self.assertEqual(row(LOCATIONS[3]["bit_index"]), [0, 1, 1, 1])
        self.assertEqual(read("message_item_names", 25 * 64, 64), bytes(rom_item_name("Hookshot")))
        self.assertEqual(read("rando_player_name_table", 32, 16).strip(), b"LINK")
        self.assertEqual(int.from_bytes(read("config_player_id", 0, 2), "little"), 1)
        self.assertEqual(int.from_bytes(read("config_remote_items", 0, 2), "little"), 0b101)
        nothing = read("locations_nothing", 0, 20)
        bit = LOCATIONS[0]["bit_index"]
        self.assertTrue(nothing[bit // 8] & (1 << (bit % 8)))
        self.assertEqual(bytes(rom[0x7FC0:0x7FC0 + 4]), b"SMMR")

    def test_incompatible_layout_rejected(self):
        base, rom = synthetic_roms()
        addr, hook = MAPRANDO_LOAD_HOOK
        rom[snes_to_pc(addr)] = 0
        with self.assertRaises(Exception):
            apply_archipelago(rom, base, {"player_ids": [0], "player_names": ["Archipelago"], "locations": [],
                                          "own_player_id": 1, "death_link": 0, "remote_items": False}, b"SMMR")
