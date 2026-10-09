import unittest

from Fill import distribute_items_restrictive
from test.general import setup_multiworld
from worlds.AutoWorld import call_all

from .. import SMMRWorld, runtime
from ..core.mwplan import OtherWorldItem, OwnItem, plan


class TestTwoMapRandoWorlds(unittest.TestCase):
    def setUp(self) -> None:
        self.multiworld = setup_multiworld([SMMRWorld, SMMRWorld], seed=7, options={"map_layout": "vanilla"})
        distribute_items_restrictive(self.multiworld)
        call_all(self.multiworld, "post_fill")

    def test_beatable_with_items_crossing_worlds(self) -> None:
        self.assertTrue(self.multiworld.can_beat_game())
        crossing = [loc for loc in self.multiworld.get_locations(1) if loc.item and loc.item.player == 2]
        self.assertTrue(crossing, "the fill put none of player 2's items in player 1's world")

    def test_the_rom_shows_a_foreign_item_where_another_world_s_item_is(self) -> None:
        world = self.multiworld.worlds[1]
        assert isinstance(world, SMMRWorld)
        placed = world.placement()
        mw = plan(runtime.catalog(), placed)
        foreign = {entry["location_idx"] for entry in mw.foreign_items}
        for index, item in enumerate(placed):
            match item:
                case OwnItem(name):
                    self.assertEqual(runtime.catalog().item(mw.item_placement[index]).name, name)
                    self.assertNotIn(index, foreign)
                case OtherWorldItem(recipient=recipient):
                    self.assertEqual(mw.item_placement[index], "Nothing")
                    self.assertIn(index, foreign)
                    self.assertEqual(recipient, self.multiworld.get_player_name(2))
