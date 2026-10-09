from test.bases import WorldTestBase


class SMMRTestBase(WorldTestBase):
    game = "Super Metroid Map Rando"
    options = {"map_layout": "vanilla"}

    def fill(self) -> None:
        """WorldTestBase stops before the fill: run it, as Main does."""
        from Fill import distribute_items_restrictive
        from worlds.AutoWorld import call_all
        distribute_items_restrictive(self.multiworld)
        call_all(self.multiworld, "post_fill")
