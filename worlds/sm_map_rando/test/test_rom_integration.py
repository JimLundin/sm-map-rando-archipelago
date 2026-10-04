"""
ROM build integration test. It needs a Super Metroid (JU) ROM: set the SMMR_TEST_ROM environment variable to its path
to run it (it is skipped otherwise).
"""
import json
import os
import unittest

from . import SMMapRandoTestBase
from ..Locations import LOCATIONS
from ..Rom import MAPRANDO_LOAD_HOOK, ap_item_plm_types, apply_archipelago, build_ap_data, snes_to_pc, \
    write_checksum

ROM_PATH = os.getenv("SMMR_TEST_ROM")


@unittest.skipUnless(ROM_PATH, "SMMR_TEST_ROM not set")
class TestRomBuild(SMMapRandoTestBase):
    options = {"wall_jump": "collectible", "speed_booster": "split", "room_theming": "vanilla"}

    def test_build_rom(self):
        from .. import native
        from ..Rom import get_base_rom_bytes
        from Fill import distribute_items_restrictive
        distribute_items_restrictive(self.multiworld)
        world = self.multiworld.worlds[1]
        base = get_base_rom_bytes(ROM_PATH)
        native.ensure_samus_sprite("samus_vanilla")
        native.ensure_mosaic_patches()
        placement, location_items, player_ids = world.get_item_placement_and_ap_data()
        randomization = dict(world.rando_output["randomization"], item_placement=placement)
        rom = bytearray(native.get_map_rando().make_rom(
            base, json.dumps(world.rando_settings), json.dumps(randomization),
            json.dumps(native_customize(world)), ap_item_plm_types()))
        addr, hook = MAPRANDO_LOAD_HOOK
        self.assertEqual(bytes(rom[snes_to_pc(addr):snes_to_pc(addr) + len(hook)]), hook)
        apply_archipelago(rom, base, build_ap_data(world, location_items, player_ids), b"SMMR_TEST")
        write_checksum(rom)
        # Every item location's PLM, in every room state where it appears, must be an AP item PLM (except our own
        # Nothing items, which Map Rando handles itself).
        ap_plms = set(ap_item_plm_types())
        nothing = {x[0] for x in location_items if x[2] == 22 and x[1] == 0}
        for loc in LOCATIONS:
            x, y, arg = base[loc["plm_ptr"] + 2], base[loc["plm_ptr"] + 3], base[loc["plm_ptr"] + 4]
            pattern = bytes([x, y, arg, base[loc["plm_ptr"] + 5]])
            found = []
            i = rom.find(pattern, 0x70000, 0x80000)
            while i != -1:
                found.append(rom[i - 2] | rom[i - 1] << 8)
                i = rom.find(pattern, i + 1, 0x80000)
            item_types = [t for t in found if t in ap_plms or 0xEED7 <= t < 0xF800]
            self.assertTrue(item_types, loc["name"])
            for t in item_types:
                if loc["bit_index"] in nothing:
                    self.assertNotIn(t, ap_plms, loc["name"])
                else:
                    self.assertIn(t, ap_plms, f"{loc['name']}: PLM {t:#06x}")


def native_customize(world):
    from ..settings_builder import build_customize_settings
    return build_customize_settings(world)
