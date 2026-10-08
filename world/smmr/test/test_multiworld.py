import unittest

from Fill import distribute_items_restrictive
from test.general import setup_multiworld
from worlds.AutoWorld import call_all

from .. import SMMRWorld, runtime
from ..core.mwplan import PlacedItem, plan


class TestTwoMapRandoWorlds(unittest.TestCase):
    def setUp(self) -> None:
        self.multiworld = setup_multiworld([SMMRWorld, SMMRWorld], seed=7, options={"map_layout": "vanilla"})
        distribute_items_restrictive(self.multiworld)
        call_all(self.multiworld, "post_fill")

    def test_beatable_with_items_crossing_worlds(self):
        self.assertTrue(self.multiworld.can_beat_game())
        crossing = [loc for loc in self.multiworld.get_locations(1) if loc.item and loc.item.player == 2]
        self.assertTrue(crossing, "the fill put none of player 2's items in player 1's world")

    def test_the_rom_shows_nothing_where_another_world_s_item_is(self):
        catalog = runtime.catalog()
        locations = {loc.name: loc for loc in self.multiworld.get_locations(1)}
        placed = [PlacedItem(locations[info.name].item.name, locations[info.name].item.player,
                             locations[info.name].item.game) for info in catalog.locations]
        placement = plan(catalog, placed, 1, SMMRWorld.game).item_placement
        for info, item, shown in zip(catalog.locations, placed, placement):
            if item.player == 1:
                self.assertEqual(catalog.item(shown).name, item.name, info.name)
            else:
                self.assertEqual(shown, "Nothing", info.name)
