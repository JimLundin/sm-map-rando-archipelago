"""ROM scenario tests: our multiworld patch on a Map Rando ROM, in a headless emulator.

They need a Super Metroid (JU) ROM (`SMMR_TEST_ROM`), a libretro SNES core (`SMMR_SNES_CORE`), the engine build and
the assembled patch (`make engine mw`). The ROM is built once per session from the recorded seed fixture, booted to
gameplay once, and each test starts from that save state.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "world" / "smmr"))
sys.path.insert(0, str(ROOT / "tools"))

from core import mwpatch  # noqa: E402
from core.abi import Abi  # noqa: E402
from core.catalog import Catalog  # noqa: E402
from local_engine import local_engine  # noqa: E402

CORE = os.environ.get("SMMR_SNES_CORE", "/tmp/snes9x/libretro/snes9x_libretro.so")
VANILLA = os.environ.get("SMMR_TEST_ROM")
GAMEPLAY = 8


@pytest.fixture(scope="session")
def abi() -> Abi:
    return Abi.parse((ROOT / "world/smmr/data/abi.toml").read_text())


@pytest.fixture(scope="session")
def map_rando_rom() -> bytes:
    if not VANILLA or not Path(CORE).exists():
        pytest.skip("needs SMMR_TEST_ROM and a libretro SNES core (SMMR_SNES_CORE)")
    engine = local_engine()
    settings = json.loads((ROOT / "fixtures/settings/default-vanilla.upgraded.json").read_text())
    seed = json.loads((ROOT / "fixtures/seeds/default-vanilla-1.json").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "mr.sfc"
        engine.rom(settings, seed["randomization"], Path(VANILLA), out)
        return out.read_bytes()


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return Catalog.from_info(json.loads((ROOT / "world/smmr/data/info.json").read_text()))


@pytest.fixture(scope="session")
def patched_rom(map_rando_rom, abi, catalog) -> bytes:
    """The ROM as the player's patch procedure makes it (S5b)."""
    return mwpatch.apply(map_rando_rom, (ROOT / "world/smmr/data/mw.ips").read_bytes(), abi, catalog,
                         mwpatch.rom_name(abi, 1, 12345))


def boot_to_gameplay(emu) -> None:
    """From power-on through the title screen and file select into a new game."""
    for i in range(300):
        emu.run(10)
        if i % 6 == 0:
            emu.press("start")
        if emu.wram.u16(0x0998) == GAMEPLAY:
            break
    else:
        pytest.fail("the ROM didn't reach gameplay")
    emu.run(60)


@pytest.fixture(scope="session")
def _emulator_and_gameplay_state(patched_rom):
    from emu import Emulator
    emu = Emulator(patched_rom, CORE)
    boot_to_gameplay(emu)
    yield emu, emu.save_state()
    emu.close()


@pytest.fixture
def game(_emulator_and_gameplay_state):
    """The emulator in gameplay, at Map Rando's start, before anything was received."""
    emu, state = _emulator_and_gameplay_state
    emu.load_state(state)
    return emu
