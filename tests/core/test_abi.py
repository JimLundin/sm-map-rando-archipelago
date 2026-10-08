from conftest import ROOT
from core import ips
from core.abi import Abi, snes_to_pc

ABI = Abi.parse((ROOT / "world/smmr/data/abi.toml").read_text())


def test_ips_round_trip():
    writes = {0x10: 1, 0x11: 2, 0x12: 3, 0x2000: 9, 0x3FFFFF: 0xAA}
    rom = bytearray(0x400000)
    ips.apply(ips.encode(writes), rom)
    assert {i: rom[i] for i in writes} == writes
    assert sum(rom) == sum(writes.values())


def test_lorom_addresses():
    assert snes_to_pc(0x808000) == 0
    assert snes_to_pc(0x828B71) == 0x10B71
    assert snes_to_pc(0x00FFC0) == 0x7FC0


def test_location_table_maps_collected_bits_back_to_locations():
    bits = [5, 0, 130]   # location index → its collected-item bit
    table = ABI.location_table(bits)
    collected = bytearray(ABI.wram["collected_items_size"])
    for bit in (130, 5):
        collected[bit >> 3] |= 1 << (bit & 7)
    assert ABI.collected_locations(bytes(collected), table) == [0, 2]


def test_mailbox_refuses_what_the_rom_cant_give():
    assert ABI.mailbox(12, 3) == bytes([12, 0, 3, 0])
    assert ABI.mailbox(ABI.items["nothing"], 3) is None
    assert ABI.mailbox(ABI.items["count"], 3) is None


def test_defines_cover_every_address():
    defines = ABI.defines()
    for name in [*ABI.wram, *ABI.rom]:
        assert f"_{name} = $" in defines
