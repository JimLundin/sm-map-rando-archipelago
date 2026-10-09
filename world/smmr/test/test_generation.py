import os
import tempfile
import zipfile
from pathlib import Path

from . import SMMRTestBase


class TestSoloGeneration(SMMRTestBase):
    def test_every_location_gets_an_item_and_the_seed_beats(self):
        self.fill()
        self.assertTrue(self.multiworld.can_beat_game())
        for location in self.multiworld.get_locations(self.player):
            self.assertIsNotNone(location.item, location.name)

    def test_patch_builds_a_rom(self):
        rom = os.environ.get("SMMR_TEST_ROM")
        if not rom:
            self.skipTest("SMMR_TEST_ROM is not set")
        from ..patch import SMMRProcedurePatch, vanilla_rom_bytes
        SMMRProcedurePatch.source_data = vanilla_rom_bytes(rom)
        self.fill()
        world = self.multiworld.worlds[self.player]
        with tempfile.TemporaryDirectory() as out:
            world.generate_output(out)
            patch_path = next(Path(out).glob("*.apsmmr"))
            self.assertIn("smmr.json", zipfile.ZipFile(patch_path).namelist())
            patch = SMMRProcedurePatch(str(patch_path))
            target = Path(out) / "out.sfc"
            patch.patch(str(target))
            self.assertEqual(len(target.read_bytes()), 0x400000)
