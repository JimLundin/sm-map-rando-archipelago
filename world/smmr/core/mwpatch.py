"""Stage S5b: Map Rando's ROM → our multiworld ROM. Pure: bytes in, bytes out."""
from __future__ import annotations

from typing import List

from . import ips
from .abi import Abi, snes_to_pc
from .catalog import Catalog


def location_bits(rom: bytes, catalog: Catalog) -> List[int]:
    """Each location's collected-item bit: its item PLM's room argument."""
    return [rom[loc.plm_addr + 4] | rom[loc.plm_addr + 5] << 8 for loc in catalog.locations]


def rom_name(abi: Abi, player: int, seed: int) -> str:
    return f"SMMR{abi.version}{player:03d}{seed % 10 ** 13:013d}"


def apply(map_rando_rom: bytes, mw_ips: bytes, abi: Abi, catalog: Catalog, name: str) -> bytes:
    rom = bytearray(map_rando_rom)
    bits = location_bits(rom, catalog)
    if len(set(bits)) != len(bits) or max(bits) >= abi.wram["collected_items_size"] * 8:
        raise ValueError("the item PLMs' room arguments aren't distinct collected-item bits")
    ips.apply(mw_ips, rom)
    for address, data in [(abi.rom["header"], abi.header()),
                          (abi.rom["location_table"], abi.location_table(bits)),
                          (abi.rom["rom_name"], abi.rom_name(name))]:
        rom[snes_to_pc(address):snes_to_pc(address) + len(data)] = data
    return bytes(rom)
