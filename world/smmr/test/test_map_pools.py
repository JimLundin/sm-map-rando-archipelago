import os

from . import SMMRTestBase


class TestSmallMapPool(SMMRTestBase):
    """A map pool layout: downloaded on first use (~190 MB), so only with SMMR_TEST_DOWNLOADS=1."""
    options = {"map_layout": "small"}

    def setUp(self) -> None:
        if not os.environ.get("SMMR_TEST_DOWNLOADS"):
            self.skipTest("set SMMR_TEST_DOWNLOADS=1 to download the Small map pool")
        super().setUp()

    def test_generates_on_a_pool_map(self):
        world = self.multiworld.worlds[self.player]
        assert world.rando_settings["map_layout"] == "Small"
        self.fill()
        self.assertTrue(self.multiworld.can_beat_game())
