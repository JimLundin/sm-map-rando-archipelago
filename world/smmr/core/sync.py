"""Stage S6's decisions, from one snapshot of the game's memory: what the client sends and writes. Pure.

The client (`client.py`) reads a `Snapshot` through SNI, calls `step`, and does what the `Actions` say.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Set, Tuple

from .abi import Abi
from .catalog import LOCATION_ID_BASE, ITEM_ID_BASE

GAMEPLAY = 0x08
FINISHED_STATES = (0x26, 0x27)   # Samus escaped Zebes; ending and credits


@dataclass(frozen=True)
class Snapshot:
    game_state: int
    collected_bits: bytes
    received_count: int


@dataclass(frozen=True)
class Received:
    item_id: int                  # Archipelago item id
    player: int                   # who sent it


@dataclass
class Actions:
    new_locations: List[int] = field(default_factory=list)       # Archipelago location ids to send
    mailbox: Optional[Tuple[int, bytes]] = None                  # (seq, item and sender words) to write
    finished: bool = False


def step(abi: Abi, location_table: bytes, snapshot: Snapshot, checked: Set[int],
         received: Sequence[Received]) -> Actions:
    actions = Actions()
    if snapshot.game_state in FINISHED_STATES:
        actions.finished = True
    if snapshot.game_state != GAMEPLAY:   # outside gameplay, WRAM may not hold a loaded save
        return actions
    for index in abi.collected_locations(snapshot.collected_bits, location_table):
        if LOCATION_ID_BASE + index not in checked:
            actions.new_locations.append(LOCATION_ID_BASE + index)
    if snapshot.received_count < len(received):
        item = received[snapshot.received_count]
        words = abi.mailbox(item.item_id - ITEM_ID_BASE, item.player)
        # An item the ROM can't give still takes its number: the ROM counts it as received.
        actions.mailbox = (snapshot.received_count + 1,
                           words if words is not None else abi.items["count"].to_bytes(2, "little") + bytes(2))
    return actions
