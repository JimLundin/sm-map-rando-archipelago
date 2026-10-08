"""Stage S5, on the player's machine: the .apsmmr patch → the ROM.

The patch holds `smmr.json` ({settings, randomization, rom_name}). Patching runs the engine's `rom` on the player's
vanilla ROM (S5a), then applies our multiworld patch on top (S5b, `core.mwpatch`).
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import Utils
from worlds.Files import APPatchExtension, APProcedurePatch

from . import runtime
from .core import mwpatch

GAME = "Super Metroid Map Rando"
SM_JU_MD5 = "21f3e98df4780ee1c667b84e57d88675"


class SMMRPatchExtension(APPatchExtension):
    game = GAME

    @staticmethod
    def smmr_build(caller: APProcedurePatch, rom: bytes, data_file: str) -> bytes:
        data = json.loads(caller.get_file(data_file))
        with tempfile.TemporaryDirectory() as tmp:
            vanilla, out = Path(tmp) / "vanilla.sfc", Path(tmp) / "out.sfc"
            vanilla.write_bytes(rom)
            runtime.engine().rom(data["settings"], data["randomization"], vanilla, out)
            map_rando_rom = out.read_bytes()
        return mwpatch.apply(map_rando_rom, runtime.data("mw.ips"), runtime.abi(), runtime.catalog(),
                             data["rom_name"])


class SMMRProcedurePatch(APProcedurePatch):
    game = GAME
    hash = SM_JU_MD5
    patch_file_ending = ".apsmmr"
    result_file_ending = ".sfc"
    procedure = [("smmr_build", ["smmr.json"])]

    @classmethod
    def get_source_data(cls) -> bytes:
        return vanilla_rom_bytes()


def vanilla_rom_bytes(file_name: str = "") -> bytes:
    from settings import get_settings
    path = file_name or get_settings().smmr_options.rom_file
    data = bytearray(Path(Utils.user_path(path)).read_bytes())
    if len(data) % 0x400 == 0x200:   # copier header
        data = data[0x200:]
    if hashlib.md5(data).hexdigest() != SM_JU_MD5:
        raise ValueError("Super Metroid Map Rando needs a Super Metroid (JU) ROM; the one provided has another hash.")
    return bytes(data)
