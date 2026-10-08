from . import SMMRTestBase


class TestCategoryOverrides(SMMRTestBase):
    options = {"map_layout": "vanilla", "skill_assumptions": "expert", "objectives": "bosses", "doors": "beam",
               "start_location": "randomized"}

    def test_overrides_reach_map_rando(self):
        world = self.multiworld.worlds[self.player]
        settings = world.rando_settings
        assert settings["skill_assumption_settings"]["preset"] == "Expert"
        assert settings["objective_settings"]["preset"] == "Bosses"
        assert settings["doors_settings"]["preset"] == "Beam"
        assert settings["start_location_settings"]["mode"] == "Random"
        self.fill()
        self.assertTrue(self.multiworld.can_beat_game())


class TestEscapeStart(SMMRTestBase):
    """An escape start places nothing: everything is reachable, nothing is needed."""
    options = {"map_layout": "vanilla", "start_location": "escape"}

    def test_generates(self):
        world = self.multiworld.worlds[self.player]
        assert world.world.escape
        self.fill()
        self.assertTrue(self.multiworld.can_beat_game())
