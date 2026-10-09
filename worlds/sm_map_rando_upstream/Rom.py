"""
ROM patching for Super Metroid Map Rando Upstream.

At generation time, the world writes everything needed to build the ROM into the patch file (`rando_data.json`):
Map Rando settings, the randomization (with the item placement adjusted for Archipelago items), cosmetic settings,
and the Archipelago tables (who gets which item, player names, ...). When the patch is applied, the ROM is built by
the native Map Rando patcher, then the Archipelago multiworld basepatch is applied on top, and the item locations are
switched to the Archipelago item PLMs.
"""
from __future__ import annotations

import hashlib
import json
import os
import pkgutil
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Tuple

import settings
import Utils
from worlds.Files import APPatchExtension, APProcedurePatch

from .Items import NOTHING_INDEX, OFFWORLD_ITEM_FIRST_ID

if TYPE_CHECKING:
    from . import SMMapRandoWorld

SMJUHASH = "21f3e98df4780ee1c667b84e57d88675"
ROM_PLAYERDATA_COUNT = 202
ROM_MAX_PLAYERID = 65535
ROM_NAME_ADDR = 0x7FC0
ROM_NAME_SIZE = 21
ITEM_NAME_COUNT = 125  # entries in message_item_names (25 Map Rando items + 100 off-world items)

# Map Rando code that the basepatch hooks: "JSL set_marker_colors" at the end of LoadGame (saveload.asm)
MAPRANDO_LOAD_HOOK = (0x81F0BF, bytes([0x22, 0x5C, 0xEA, 0x8F]))

def snes_to_pc(address: int) -> int:
    return ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)


def get_base_rom_path(file_name: str = "") -> str:
    options: settings.Settings = settings.get_settings()
    if not file_name:
        file_name = options.sm_map_rando_upstream_options.rom_file
    if not os.path.exists(file_name):
        file_name = Utils.user_path(file_name)
    return file_name


def get_base_rom_bytes(file_name: str = "") -> bytes:
    base_rom_bytes = getattr(get_base_rom_bytes, "base_rom_bytes", None)
    if not base_rom_bytes:
        file_name = get_base_rom_path(file_name)
        with open(file_name, "rb") as f:
            base_rom_bytes = bytes(Utils.read_snes_rom(f))
        if hashlib.md5(base_rom_bytes).hexdigest() != SMJUHASH:
            raise Exception("Supplied Base Rom does not match known MD5 for Super Metroid (Japan, USA). "
                            "Get the correct game and version, then dump it")
        get_base_rom_bytes.base_rom_bytes = base_rom_bytes
    return base_rom_bytes


def get_symbols() -> Dict[str, int]:
    """AP basepatch symbols, as SNES addresses."""
    symbols = json.loads(pkgutil.get_data(__name__, "data/SMBasepatch_prebuilt/sm-basepatch-symbols.json"))
    out = {}
    for name, addr in symbols.items():
        bank, offset = addr.split(":")
        out[name] = (int(bank, 16) << 16) | int(offset, 16)
    return out


def word(value: int) -> List[int]:
    return [value & 0xFF, (value >> 8) & 0xFF]


ROM_CHAR_MAP = {
    "A": 0x2CC0, "B": 0x2CC1, "C": 0x2CC2, "D": 0x2CC3, "E": 0x2CC4, "F": 0x2CC5, "G": 0x2CC6, "H": 0x2CC7,
    "I": 0x2CC8, "J": 0x2CC9, "K": 0x2CCA, "L": 0x2CCB, "M": 0x2CCC, "N": 0x2CCD, "O": 0x2CCE, "P": 0x2CCF,
    "Q": 0x2CD0, "R": 0x2CD1, "S": 0x2CD2, "T": 0x2CD3, "U": 0x2CD4, "V": 0x2CD5, "W": 0x2CD6, "X": 0x2CD7,
    "Y": 0x2CD8, "Z": 0x2CD9, " ": 0x2C0F, "!": 0x2CDF, "?": 0x2CDE, "'": 0x2CDD, ",": 0x2CDA, ".": 0x2CDA,
    "-": 0x2CDD, "_": 0x000F, "1": 0x2C01, "2": 0x2C02, "3": 0x2C03, "4": 0x2C04, "5": 0x2C05, "6": 0x2C06,
    "7": 0x2C07, "8": 0x2C08, "9": 0x2C09, "0": 0x2C00, "%": 0x2C0A,
}


def rom_item_name(item_name: str) -> List[int]:
    """An item name as a message box line (32 tiles)."""
    text = "___" + item_name.upper()[:26].strip().center(26, " ") + "___"
    data = []
    for char in text:
        data.extend(word(ROM_CHAR_MAP.get(char, 0x2CDE)))
    return data


def rom_player_name(player_name: str) -> bytes:
    return player_name[:16].upper().center(16).encode("ascii", "replace")


def credits_text(text: str) -> str:
    """Text for the item credits (only letters and spaces are shown)."""
    return "".join(c for c in text.upper() if c.isascii() and (c.isalpha() or c == " "))[:20].strip()


def build_ap_data(world: "SMMapRandoWorld", location_items: List[Tuple[int, int, Optional[int], bool, str, int]],
                  player_ids: List[int]) -> Dict[str, Any]:
    """
    Archipelago tables for the patch.
    location_items: for each own location (bit index, destination type, item id or None for an off-world item,
                    advancement, item name, destination player)
    player_ids: sorted AP player ids that appear in the tables (index 0 must be 0 = "Archipelago")
    """
    multiworld = world.multiworld
    names = []
    for pid in player_ids:
        names.append("Archipelago" if pid == 0 else multiworld.get_player_name(pid))
    return {
        "player_ids": [pid if pid <= ROM_MAX_PLAYERID else 0 for pid in player_ids],
        "player_names": names,
        "locations": [list(x) for x in location_items],
        "own_player_id": world.player,
        "death_link": world.options.death_link.value,
        "remote_items": bool(world.options.remote_items.value),
    }


class SMMapRandoProcedurePatch(APProcedurePatch):
    hash = SMJUHASH
    game = "Super Metroid Map Rando Upstream"
    patch_file_ending = ".apsmmru"
    result_file_ending = ".sfc"

    procedure = [
        ("patch_rom", ["rando_data.json"]),
    ]

    @classmethod
    def get_source_data(cls) -> bytes:
        return get_base_rom_bytes()


def apply_ips(rom: bytearray, patch: bytes) -> None:
    assert patch[:5] == b"PATCH", "Invalid IPS patch"
    i = 5
    while patch[i:i + 3] != b"EOF":
        offset = int.from_bytes(patch[i:i + 3], "big")
        size = int.from_bytes(patch[i + 3:i + 5], "big")
        i += 5
        if size == 0:
            rle_size = int.from_bytes(patch[i:i + 2], "big")
            data = patch[i + 2:i + 3] * rle_size
            i += 3
        else:
            data = patch[i:i + size]
            i += size
        if offset + len(data) > len(rom):
            rom.extend(bytes(offset + len(data) - len(rom)))
        rom[offset:offset + len(data)] = data


def write_checksum(rom: bytearray) -> None:
    def checksum_mirror_sum(start, length, mask=0x800000):
        while not (length & mask) and mask:
            mask >>= 1
        part1 = sum(start[:mask]) & 0xFFFF
        part2 = 0
        next_length = length - mask
        if next_length:
            part2 = checksum_mirror_sum(start[mask:], next_length, mask >> 1)
            while next_length < mask:
                next_length += next_length
                part2 += part2
        return (part1 + part2) & 0xFFFF

    crc = checksum_mirror_sum(rom, len(rom))
    inv = crc ^ 0xFFFF
    rom[0x7FDC:0x7FE0] = bytes([inv & 0xFF, (inv >> 8) & 0xFF, crc & 0xFF, (crc >> 8) & 0xFF])


def ap_item_plm_types() -> List[int]:
    """The AP item PLM types (visible, chozo orb, shot block), used by Map Rando's patcher for all item locations
    (except locations with our own Nothing items). They look up the item to show and give in rando_item_table."""
    sym = get_symbols()
    return [sym[f"archipelago_{kind}_item_plm"] & 0xFFFF for kind in ("visible", "chozo", "hidden")]


def apply_archipelago(rom: bytearray, base_rom: bytes, ap: Dict[str, Any], rom_name: bytes) -> None:
    """Apply the AP basepatch and the multiworld tables to a ROM produced by the Map Rando patcher."""
    hook_addr, hook_bytes = MAPRANDO_LOAD_HOOK
    pc = snes_to_pc(hook_addr)
    if bytes(rom[pc:pc + len(hook_bytes)]) != hook_bytes:
        raise Exception("Unexpected Map Rando ROM layout: the Archipelago basepatch is incompatible with this "
                        "version of the Map Rando patcher.")

    apply_ips(rom, pkgutil.get_data(__name__, "data/SMBasepatch_prebuilt/multiworld-basepatch.ips"))
    sym = get_symbols()

    def write(symbol: str, offset: int, values: Iterable[int]) -> None:
        addr = snes_to_pc(sym[symbol]) + offset
        values = bytes(values)
        rom[addr:addr + len(values)] = values

    # Players
    player_ids: List[int] = ap["player_ids"]
    player_index = {pid: i for i, pid in enumerate(player_ids)}
    for i, (pid, name) in enumerate(zip(player_ids, ap["player_names"])):
        write("rando_player_name_table", i * 16, rom_player_name(name))
        write("rando_player_id_table", i * 2, word(pid))

    # Items at our locations
    locations_nothing = bytearray(20)
    offworld_idx = 0
    for bit_index, dest_type, item_id, advancement, item_name, dest_player in ap["locations"]:
        if item_id is None:
            # off-world item: its name gets its own message table entry
            item_id = OFFWORLD_ITEM_FIRST_ID + offworld_idx
            assert item_id < ITEM_NAME_COUNT
            write("message_item_names", item_id * 64, rom_item_name(item_name))
            offworld_idx += 1
        elif item_id == NOTHING_INDEX and dest_type == 0:
            locations_nothing[bit_index // 8] |= 1 << (bit_index % 8)
        write("rando_item_table", bit_index * 8,
              word(dest_type) + word(item_id) + word(player_index.get(dest_player, 0)) + word(0 if advancement else 1))
    write("locations_nothing", 0, locations_nothing)

    # Off-world item graphics
    for file_name, palette_symbol, data_symbol in [
        ("off_world_prog_item.bin", "prog_item_eight_palette_indices", "offworld_graphics_data_progression_item"),
        ("off_world_item.bin", "nonprog_item_eight_palette_indices", "offworld_graphics_data_item"),
    ]:
        data = pkgutil.get_data(__name__, f"data/custom_sprite/{file_name}")
        write(palette_symbol, 0, data[0:8])
        write(data_symbol, 0, data[8:264])

    # Config
    write("config_deathlink", 0, [ap["death_link"]])
    # Archipelago items_handling flags: other worlds' items and starting inventory are always sent by the server;
    # our own world's items too if remote items is enabled. (The basepatch only checks the 0b010 bit.)
    write("config_remote_items", 0, word(0b101 | (0b010 if ap["remote_items"] else 0)))
    write("config_player_id", 0, word(ap["own_player_id"]))

    rom[ROM_NAME_ADDR:ROM_NAME_ADDR + ROM_NAME_SIZE] = rom_name.ljust(ROM_NAME_SIZE, b"\0")[:ROM_NAME_SIZE]


class SMMapRandoPatchExtensions(APPatchExtension):
    game = "Super Metroid Map Rando Upstream"

    @staticmethod
    def patch_rom(caller: APProcedurePatch, rom: bytes, rando_data_file: str) -> bytes:
        from . import native
        data = json.loads(caller.get_file(rando_data_file).decode("utf-8"))
        customize = data["customize"]
        native.ensure_samus_sprite(customize["samus_sprite"])
        native.ensure_mosaic_patches()  # needed by Map Rando's patcher for all room themes
        base_rom = bytes(rom)
        patched = native.get_map_rando().make_rom(
            base_rom,
            json.dumps(data["settings"]),
            json.dumps(data["randomization"]),
            json.dumps(customize),
            ap_item_plm_types(),
        )
        out = bytearray(patched)
        apply_archipelago(out, base_rom, data["ap"], bytes(data["rom_name"], "ascii"))
        write_checksum(out)
        return bytes(out)

