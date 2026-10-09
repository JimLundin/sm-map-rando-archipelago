"""The engine port: the only way the world calls Map Rando.

`SubprocessEngine` runs the `smmr-engine` binary (see `engine/src/main.rs`) as one long-lived `serve` process, so
Map Rando's data is loaded once per generation rather than per call. Requests and responses are JSON lines;
responses start with the byte 1E, since Map Rando prints progress to stdout too.
"""
from __future__ import annotations

import json
import platform
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import IO, Any, Protocol, Self, TypeAlias

from .logic import Inventory, Reach

RESPONSE = b"\x1e"

JsonObject: TypeAlias = dict[str, Any]      # Map Rando's own data (settings, a world): only the engine reads it


@dataclass(frozen=True, slots=True)
class GeneratedWorld:
    """The engine's `world`: everything but the item placement."""
    world: JsonObject                        # given back to the engine as it is (`open`, `rom`)
    seed_hash: str
    pool: dict[str, int]                     # the items to place: Map Rando item name → count
    locations: list[int]                     # the item locations in the map's rooms
    starting_items: dict[str, int]
    escape: bool                             # Samus starts in the escape with every item: nothing to place

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Self:
        return cls(data["world"], data["seed_hash"], dict(data["pool"]), list(data["locations"]),
                   {item: count for item, count in data["starting_items"].items() if count}, data["escape"])


def platform_tag() -> str:
    """Names the engine build for this machine in the .apworld's bin/ (e.g. linux-x86_64, win32-amd64)."""
    return f"{sys.platform}-{platform.machine().lower()}"


class EngineError(Exception):
    """Map Rando rejected the request (invalid settings, randomization failed, ...)."""


class Engine(Protocol):
    def info(self) -> dict[str, Any]: ...

    def upgrade(self, settings: Mapping[str, Any]) -> dict[str, Any]: ...

    def randomize(self, settings: Mapping[str, Any], seed: int) -> dict[str, Any]: ...

    def world(self, settings: Mapping[str, Any], seed: int) -> GeneratedWorld: ...

    def open(self, settings: Mapping[str, Any], world: JsonObject) -> int: ...

    def reach(self, session: int, inventories: Sequence[Inventory]) -> list[Reach]: ...

    def rom(self, settings: Mapping[str, Any], randomization: Mapping[str, Any], rom: Path, out: Path) -> None: ...

    def rom_from_world(self, settings: Mapping[str, Any], world: JsonObject, item_placement: Sequence[str],
                       foreign_items: Sequence[Mapping[str, Any]], rom: Path, out: Path) -> None: ...


class SubprocessEngine:
    def __init__(self, binary: Path, data_dir: Path, maps_dir: Path | None = None):
        self.binary = Path(binary)
        self.data_dir = Path(data_dir)
        self.maps_dir = maps_dir
        self._process: subprocess.Popen[bytes] | None = None
        self._stderr: IO[bytes] | None = None
        self._lock = threading.Lock()

    def _start(self) -> subprocess.Popen[bytes]:
        if self._process is None or self._process.poll() is not None:
            self._stderr = tempfile.TemporaryFile()
            self._process = subprocess.Popen([str(self.binary), "--data", str(self.data_dir.resolve()), "serve"],
                                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._stderr)
        return self._process

    def call(self, command: str, request: Mapping[str, Any]) -> Any:
        with self._lock:
            process = self._start()
            assert process.stdin is not None and process.stdout is not None
            try:
                process.stdin.write(json.dumps({**request, "command": command}).encode() + b"\n")
                process.stdin.flush()
                while not (line := process.stdout.readline()).startswith(RESPONSE):
                    if not line:   # the engine exited
                        raise BrokenPipeError
            except OSError:
                raise RuntimeError(f"smmr-engine crashed during {command}: {self._error_output()}") from None
        response = json.loads(line[1:])
        if "error" in response:
            raise EngineError(response["error"])
        return response["ok"]

    def _error_output(self) -> str:
        if self._process is not None:
            self._process.wait(timeout=10)
        assert self._stderr is not None
        self._stderr.seek(0)
        return self._stderr.read().decode(errors="replace")[-2000:]

    def close(self) -> None:
        if self._process is not None and self._process.poll() is None:
            assert self._process.stdin is not None
            self._process.stdin.close()
            self._process.wait(timeout=10)
        if self._stderr is not None:
            self._stderr.close()

    def info(self) -> dict[str, Any]:
        return self.call("info", {})

    def upgrade(self, settings: Mapping[str, Any]) -> dict[str, Any]:
        return self.call("upgrade", {"settings": settings})["settings"]

    def randomize(self, settings: Mapping[str, Any], seed: int) -> dict[str, Any]:
        return self.call("randomize", self._with_maps({"settings": settings, "seed": seed}))

    def world(self, settings: Mapping[str, Any], seed: int) -> GeneratedWorld:
        return GeneratedWorld.from_json(self.call("world", self._with_maps({"settings": settings, "seed": seed})))

    def open(self, settings: Mapping[str, Any], world: JsonObject) -> int:
        """Sets up the world's logic in the engine process, for `reach`."""
        return self.call("open", {"settings": settings, "world": world})["session"]

    def reach(self, session: int, inventories: Sequence[Inventory]) -> list[Reach]:
        """For each inventory (on top of the starting items), what it makes reachable."""
        answers = self.call("reach", {"session": session, "inventories": [dict(x) for x in inventories]})
        return [Reach(frozenset(answer["locations"]), answer["beatable"]) for answer in answers]

    def _with_maps(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.maps_dir is not None:
            request["maps_dir"] = str(Path(self.maps_dir).resolve())
        return request

    def rom(self, settings: Mapping[str, Any], randomization: Mapping[str, Any], rom: Path, out: Path) -> None:
        self.call("rom", {"settings": settings, "randomization": randomization,
                          "rom": str(Path(rom).resolve()), "out": str(Path(out).resolve())})

    def rom_from_world(self, settings: Mapping[str, Any], world: JsonObject, item_placement: Sequence[str],
                       foreign_items: Sequence[Mapping[str, Any]], rom: Path, out: Path) -> None:
        self.call("rom", {"settings": settings, "world": world, "item_placement": list(item_placement),
                          "foreign_items": list(foreign_items),
                          "rom": str(Path(rom).resolve()), "out": str(Path(out).resolve())})
