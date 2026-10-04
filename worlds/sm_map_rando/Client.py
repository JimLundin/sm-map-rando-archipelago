from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Optional

from NetUtils import ClientStatus, color
from worlds.AutoSNIClient import SNIClient

from .Locations import LOCATIONS_START_ID, location_name_to_id
from .Items import ITEMS_START_ID

if TYPE_CHECKING:
    from SNIClient import SNIContext

snes_logger = logging.getLogger("SNES")

# FXPAK Pro protocol memory mapping used by SNI
ROM_START = 0x000000
WRAM_START = 0xF50000
SRAM_START = 0xE00000

ROMNAME_START = ROM_START + 0x007FC0
ROMNAME_SIZE = 0x15
ROMNAME_PREFIX = b"SMMR"

SM_INGAME_MODES = {0x08}
SM_ENDGAME_MODES = {0x26, 0x27}
SM_DEATH_MODES = {0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A}

# RECV and SEND are from the gameplay's perspective: SNIClient writes to the RECV queue.
# (These must match the SRAM addresses in the basepatch, SMBasepatch/romhacks/maprando/main.asm)
SM_RECV_QUEUE_START = SRAM_START + 0x2640
SM_RECV_QUEUE_WCOUNT = SRAM_START + 0x2644

SM_RECV_QUEUE_COMPLETED_COUNT = WRAM_START + 0xD8AE

SM_CONFIG_START = ROM_START + 0x277F00  # $CE:FF00 (config.asm)
SM_DEATH_LINK_ACTIVE_ADDR = SM_CONFIG_START + 0x04  # 1 byte
SM_REMOTE_ITEM_FLAG_ADDR = SM_CONFIG_START + 0x06  # 1 byte

SM_ITEM_COLLECTED_PTR = WRAM_START + 0xD870
SM_ITEM_COLLECTED_SIZE = 0x14  # 20 bytes

SM_ROM_MAX_PLAYERID = 65535


def _nothing_bitmask_rom_addr() -> int:
    from .Rom import get_symbols, snes_to_pc
    return ROM_START + snes_to_pc(get_symbols()["locations_nothing"])


class SMMapRandoSNIClient(SNIClient):
    game = "Super Metroid Map Rando"
    patch_suffix = ".apsmmr"

    def __init__(self) -> None:
        super().__init__()
        self.cached_collected: Optional[bytes] = None
        self.nothing_bitmask: Optional[bytes] = None
        self.collected_mask = bytearray(SM_ITEM_COLLECTED_SIZE)
        for location_id in location_name_to_id.values():
            bit = location_id - LOCATIONS_START_ID
            self.collected_mask[bit // 8] |= 1 << (bit % 8)

    async def deathlink_kill_player(self, ctx: "SNIContext") -> None:
        from SNIClient import DeathState, snes_buffered_write, snes_flush_writes, snes_read
        snes_buffered_write(ctx, WRAM_START + 0x09C2, bytes([1, 0]))  # set current health to 1 (to prevent saving with 0 energy)
        snes_buffered_write(ctx, WRAM_START + 0x0A50, bytes([255]))  # deal 255 of damage at next opportunity
        if not ctx.death_link_allow_survive:
            snes_buffered_write(ctx, WRAM_START + 0x09D6, bytes([0, 0]))  # set current reserve to 0

        await snes_flush_writes(ctx)
        await asyncio.sleep(1)

        gamemode = await snes_read(ctx, WRAM_START + 0x0998, 1)
        health = await snes_read(ctx, WRAM_START + 0x09C2, 2)
        if health is not None:
            health = health[0] | (health[1] << 8)
        if not gamemode or gamemode[0] in SM_DEATH_MODES or (
                ctx.death_link_allow_survive and health is not None and health > 0):
            ctx.death_state = DeathState.dead

    async def validate_rom(self, ctx: "SNIContext") -> bool:
        from SNIClient import snes_read

        rom_name = await snes_read(ctx, ROMNAME_START, ROMNAME_SIZE)
        if rom_name is None or rom_name == bytes([0] * ROMNAME_SIZE) or rom_name[:4] != ROMNAME_PREFIX:
            return False

        ctx.game = self.game

        item_handling = await snes_read(ctx, SM_REMOTE_ITEM_FLAG_ADDR, 1)
        ctx.items_handling = 0b001 if item_handling is None else item_handling[0]

        ctx.rom = rom_name
        self.cached_collected = None
        self.nothing_bitmask = None

        death_link = await snes_read(ctx, SM_DEATH_LINK_ACTIVE_ADDR, 1)
        if death_link:
            ctx.allow_collect = bool(death_link[0] & 0b100)
            ctx.death_link_allow_survive = bool(death_link[0] & 0b10)
            await ctx.update_death_link(bool(death_link[0] & 0b1))

        return True

    async def game_watcher(self, ctx: "SNIContext") -> None:
        from SNIClient import snes_buffered_write, snes_flush_writes, snes_read
        if ctx.server is None or ctx.slot is None:
            # not successfully connected to a multiworld server, cannot process the game sending items
            return

        gamemode = await snes_read(ctx, WRAM_START + 0x0998, 1)
        if "DeathLink" in ctx.tags and gamemode and ctx.last_death_link + 1 < time.time():
            currently_dead = gamemode[0] in SM_DEATH_MODES
            await ctx.handle_deathlink_state(currently_dead)
        if gamemode is None:
            return
        if gamemode[0] in SM_ENDGAME_MODES:
            if not ctx.finished_game:
                await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
                ctx.finished_game = True
            return
        if gamemode[0] not in SM_INGAME_MODES:
            return

        if self.nothing_bitmask is None:
            self.nothing_bitmask = await snes_read(ctx, _nothing_bitmask_rom_addr(), SM_ITEM_COLLECTED_SIZE)
            if self.nothing_bitmask is None:
                return

        # Location checks: the game's item collected bits (excluding locations holding our own Nothing items,
        # which Map Rando marks as collected from the start).
        collected = await snes_read(ctx, SM_ITEM_COLLECTED_PTR, SM_ITEM_COLLECTED_SIZE)
        if collected is None:
            return
        collected = bytes(b & m & ~n for b, m, n in zip(collected, self.collected_mask, self.nothing_bitmask))
        if collected != self.cached_collected:
            new_checks = []
            for location_id in location_name_to_id.values():
                bit = location_id - LOCATIONS_START_ID
                if collected[bit // 8] & (1 << (bit % 8)) and location_id not in ctx.locations_checked:
                    ctx.locations_checked.add(location_id)
                    new_checks.append(location_id)
                    location = ctx.location_names.lookup_in_game(location_id)
                    snes_logger.info(
                        f"New Check: {location} "
                        f"({len(ctx.locations_checked)}/{len(ctx.missing_locations) + len(ctx.checked_locations)})")
            if new_checks:
                await ctx.send_msgs([{"cmd": "LocationChecks", "locations": new_checks}])
            self.cached_collected = collected

        # Receiving items: the game processes one queued item at a time. We write the next item once the game has
        # caught up with the previous one (its receive count, saved with the save file, equals the write count).
        completed = await snes_read(ctx, SM_RECV_QUEUE_COMPLETED_COUNT, 2)
        written = await snes_read(ctx, SM_RECV_QUEUE_WCOUNT, 2)
        if completed is None or written is None:
            return
        item_out_ptr = completed[0] | (completed[1] << 8)
        written_ptr = written[0] | (written[1] << 8)

        if item_out_ptr < len(ctx.items_received) and item_out_ptr == written_ptr:
            item = ctx.items_received[item_out_ptr]
            item_id = item.item - ITEMS_START_ID
            if bool(ctx.items_handling & 0b010) or item.location < 0:  # item.location < 0 for !getitem to work
                location_id = (item.location - LOCATIONS_START_ID) \
                    if (item.location >= 0 and item.player == ctx.slot) else 0xFF
            else:
                location_id = 0x00  # backward compat

            player_id = item.player if item.player <= SM_ROM_MAX_PLAYERID else 0
            snes_buffered_write(ctx, SM_RECV_QUEUE_START, bytes(
                [player_id & 0xFF, (player_id >> 8) & 0xFF, item_id & 0xFF, location_id & 0xFF]))
            item_out_ptr += 1
            snes_buffered_write(ctx, SM_RECV_QUEUE_WCOUNT, bytes([item_out_ptr & 0xFF, (item_out_ptr >> 8) & 0xFF]))
            logging.info("Received %s from %s (%s) (%d/%d in list)" % (
                color(ctx.item_names.lookup_in_game(item.item), "red", "bold"),
                color(ctx.player_names[item.player], "yellow"),
                ctx.location_names.lookup_in_slot(item.location, item.player), item_out_ptr,
                len(ctx.items_received)))

        await snes_flush_writes(ctx)
