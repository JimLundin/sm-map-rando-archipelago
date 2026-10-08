"""The ROM ABI (`data/abi.toml`): the multiworld patch's addresses and the codecs the patcher and the client share."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence


def snes_to_pc(address: int) -> int:
    """LoROM: bank & 7Fh is the 32 KiB page, the upper half of the bank is the data."""
    return ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)


@dataclass(frozen=True)
class Abi:
    version: int
    wram: Mapping[str, int]
    rom: Mapping[str, int]
    items: Mapping[str, int]

    @staticmethod
    def parse(text: str) -> "Abi":
        data: Dict[str, Any] = tomllib.loads(text)
        return Abi(data["version"], data["wram"], data["rom"], data["items"])

    # Patcher ---------------------------------------------------------------------------------------------------

    def location_table(self, location_bits: Sequence[int]) -> bytes:
        """The ROM table mapping collected-item bits to location indexes (`location_bits[index]` is the bit)."""
        table = bytearray([0xFF]) * (self.wram["collected_items_size"] * 8)
        for index, bit in enumerate(location_bits):
            table[bit] = index
        return bytes(table)

    def header(self) -> bytes:
        return self.version.to_bytes(2, "little")

    def rom_name(self, name: str) -> bytes:
        encoded = name.encode("ascii")
        size = self.rom["rom_name_size"]
        if len(encoded) > size:
            raise ValueError(f"ROM name {name!r} is longer than {size} bytes")
        return encoded.ljust(size, b" ")

    # Client ----------------------------------------------------------------------------------------------------

    def collected_locations(self, collected_bits: bytes, location_table: bytes) -> List[int]:
        """Location indexes whose collected-item bit is set."""
        found = []
        for bit, index in enumerate(location_table):
            if index != 0xFF and collected_bits[bit >> 3] >> (bit & 7) & 1:
                found.append(index)
        return sorted(found)

    def mailbox(self, item: int, sender: int) -> Optional[bytes]:
        """The mailbox's item and sender words, or None if the ROM can't receive that item. The client writes them
        before the seq word, so the ROM never sees a half-written item."""
        if not 0 <= item < self.items["count"] or item == self.items["nothing"]:
            return None
        return item.to_bytes(2, "little") + sender.to_bytes(2, "little")

    def defines(self) -> str:
        """asar defines for the multiworld patch."""
        lines = [f"!abi_version = {self.version}"]
        lines += [f"!wram_{name} = ${value:04X}" for name, value in self.wram.items()]
        lines += [f"!rom_{name} = ${value:06X}" for name, value in self.rom.items()]
        lines += [f"!items_{name} = {value}" for name, value in self.items.items()]
        return "\n".join(lines) + "\n"
