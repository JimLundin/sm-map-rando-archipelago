from conftest import GAMEPLAY


def test_the_rom_passes_map_randos_self_check(game):
    """Map Rando's ROM verifies its checksum in idle time (self_check.asm) and stops if it doesn't match."""
    start = game.wram.u16(0x05B6)
    game.run(60 * 60)
    assert game.wram.u16(0x0998) == GAMEPLAY
    assert (game.wram.u16(0x05B6) - start) & 0xFFFF == 60 * 60
