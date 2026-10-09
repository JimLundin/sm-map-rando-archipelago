"""The SNI client adapter: SNI reads and writes around `core.sync.step`. It decides nothing itself."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, assert_never

from NetUtils import ClientStatus
from worlds.AutoSNIClient import SNIClient

from . import runtime
from .core.abi import snes_to_pc as pc
from .core.sync import Deliver, Goal, Received, SendLocations, Snapshot, step

if TYPE_CHECKING:
    from SNIClient import SNIContext

logger = logging.getLogger("Client")
ROM_START, WRAM_START = 0x000000, 0xF50000
OWN_AND_START_ITEMS_ARE_GIVEN_BY_THE_GAME = 0b101   # receive other worlds' items and the starting inventory


class SMMRClient(SNIClient):
    game = "Super Metroid Map Rando"
    patch_suffix = ".apsmmr"

    def __init__(self) -> None:
        self.location_table: bytes | None = None

    async def validate_rom(self, ctx: "SNIContext") -> bool:
        from SNIClient import snes_read
        abi = runtime.abi()
        size = abi.rom["rom_name_size"]
        name = await snes_read(ctx, ROM_START + pc(abi.rom["rom_name"]), size)
        if name is None or not name.startswith(b"SMMR"):
            return False
        header = await snes_read(ctx, ROM_START + pc(abi.rom["header"]), 2)
        if header != abi.header():
            logger.error("This ROM was patched by another version of Super Metroid Map Rando; use the matching "
                         "version of the world, or regenerate.")
            return False
        table = await snes_read(ctx, ROM_START + pc(abi.rom["location_table"]),
                                abi.wram["collected_items_size"] * 8)
        if table is None:
            return False
        self.location_table = table
        ctx.game = self.game
        ctx.items_handling = OWN_AND_START_ITEMS_ARE_GIVEN_BY_THE_GAME
        ctx.rom = name
        return True

    async def game_watcher(self, ctx: "SNIContext") -> None:
        from SNIClient import snes_buffered_write, snes_flush_writes, snes_read
        if ctx.server is None or ctx.slot is None or self.location_table is None:
            return
        abi = runtime.abi()
        wram = abi.wram
        game_state = await snes_read(ctx, WRAM_START + wram["game_state"], 2)
        bits = await snes_read(ctx, WRAM_START + wram["collected_items"], wram["collected_items_size"])
        count = await snes_read(ctx, WRAM_START + wram["received_count"], 2)
        if game_state is None or bits is None or count is None:
            return
        snapshot = Snapshot(int.from_bytes(game_state, "little"), bits, int.from_bytes(count, "little"))
        received = [Received(item.item, item.player) for item in ctx.items_received]
        for action in step(abi, self.location_table, snapshot, ctx.locations_checked, received):
            match action:
                case SendLocations(location_ids):
                    ctx.locations_checked |= set(location_ids)
                    await ctx.send_msgs([{"cmd": "LocationChecks", "locations": list(location_ids)}])
                case Deliver(seq, words):
                    snes_buffered_write(ctx, WRAM_START + wram["mailbox_item"], words)
                    await snes_flush_writes(ctx)
                    snes_buffered_write(ctx, WRAM_START + wram["mailbox_seq"], seq.to_bytes(2, "little"))
                    await snes_flush_writes(ctx)
                case Goal():
                    if not ctx.finished_game:
                        ctx.finished_game = True
                        await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
                case _:
                    assert_never(action)
