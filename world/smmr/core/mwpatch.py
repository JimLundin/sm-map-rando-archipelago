"""Stage S5b: Map Rando's ROM → our multiworld ROM. Pure: bytes in, bytes out."""
from __future__ import annotations



from . import ips
from .abi import Abi, snes_to_pc
from .catalog import Catalog


def location_bits(rom: bytes | bytearray, catalog: Catalog) -> list[int]:
    """Each location's collected-item bit: its item PLM's room argument."""
    return [rom[loc.plm_addr + 4] | rom[loc.plm_addr + 5] << 8 for loc in catalog.locations]


def rom_name(abi: Abi, player: int, seed: int) -> str:
    return f"SMMR{abi.version}{player:03d}{seed % 10 ** 13:013d}"


CHECKSUM = 0x7FDC   # LoROM header: u16 checksum complement, then u16 checksum


def fix_checksum(rom: bytearray) -> None:
    """Recompute the header checksum, as Map Rando's patcher does: its ROM checks itself (patches/src/self_check.asm)
    and stops with "SELF CHECK FAIL" if the checksum doesn't match."""
    rom[CHECKSUM:CHECKSUM + 4] = b"\xff\xff\x00\x00"
    checksum = sum(rom) & 0xFFFF
    rom[CHECKSUM:CHECKSUM + 4] = (checksum ^ 0xFFFF).to_bytes(2, "little") + checksum.to_bytes(2, "little")


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
    fix_checksum(rom)
    return bytes(rom)
