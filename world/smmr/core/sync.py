"""Stage S6's decisions, from one snapshot of the game's memory: what the client sends and writes. Pure.

The client (`client.py`) reads a `Snapshot` through SNI, calls `step`, and performs the `Action`s it returns.
"""
from __future__ import annotations

from collections.abc import Sequence, Set
from dataclasses import dataclass


from .abi import Abi
from .catalog import ITEM_ID_BASE, LOCATION_ID_BASE

GAMEPLAY = 0x08
FINISHED_STATES = (0x26, 0x27)   # Samus escaped Zebes; ending and credits


@dataclass(frozen=True, slots=True)
class Snapshot:
    game_state: int
    collected_bits: bytes
    received_count: int


@dataclass(frozen=True, slots=True)
class Received:
    item_id: int                  # Archipelago item id
    player: int                   # who sent it


@dataclass(frozen=True, slots=True)
class SendLocations:
    """Tell the server these locations were checked."""
    location_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Deliver:
    """Write a received item to the mailbox: its item and sender words, then its number."""
    seq: int
    words: bytes


@dataclass(frozen=True, slots=True)
class Goal:
    """Samus escaped: the goal is reached."""


type Action = SendLocations | Deliver | Goal


def step(abi: Abi, location_table: bytes, snapshot: Snapshot, checked: Set[int],
         received: Sequence[Received]) -> list[Action]:
    actions: list[Action] = []
    if snapshot.game_state in FINISHED_STATES:
        actions.append(Goal())
    if snapshot.game_state != GAMEPLAY:   # outside gameplay, WRAM may not hold a loaded save
        return actions
    new = tuple(LOCATION_ID_BASE + index for index in abi.collected_locations(snapshot.collected_bits, location_table)
                if LOCATION_ID_BASE + index not in checked)
    if new:
        actions.append(SendLocations(new))
    if snapshot.received_count < len(received):
        item = received[snapshot.received_count]
        words = abi.mailbox(item.item_id - ITEM_ID_BASE, item.player)
        # An item the ROM can't give still takes its number: the ROM counts it as received.
        actions.append(Deliver(snapshot.received_count + 1,
                               words if words is not None else abi.items["count"].to_bytes(2, "little") + bytes(2)))
    return actions
