from core.mwpatch import CHECKSUM, fix_checksum


def test_the_checksum_is_the_sum_of_the_rom_and_its_complement_is_stored_with_it():
    rom = bytearray(range(256)) * (0x400000 // 256)
    fix_checksum(rom)
    complement = int.from_bytes(rom[CHECKSUM:CHECKSUM + 2], "little")
    checksum = int.from_bytes(rom[CHECKSUM + 2:CHECKSUM + 4], "little")
    assert complement ^ checksum == 0xFFFF
    assert sum(rom) & 0xFFFF == checksum   # the complement and checksum bytes add up to 2 * 0xFF


def test_fixing_twice_changes_nothing():
    rom = bytearray(0x400000)
    rom[0x1234] = 7
    fix_checksum(rom)
    once = bytes(rom)
    fix_checksum(rom)
    assert bytes(rom) == once
