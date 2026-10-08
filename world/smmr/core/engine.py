"""The engine port: the only way the world calls Map Rando.

`SubprocessEngine` runs the `smmr-engine` binary (see `engine/src/main.rs`) with one JSON request per call. Tests use
`RecordedEngine`, which replays responses recorded from the real engine (`tools/record_fixtures.py`).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Protocol


class EngineError(Exception):
    """Map Rando rejected the request (invalid settings, randomization failed, ...)."""


class Engine(Protocol):
    def info(self) -> Dict[str, Any]: ...

    def upgrade(self, settings: Mapping[str, Any]) -> Dict[str, Any]: ...

    def randomize(self, settings: Mapping[str, Any], seed: int) -> Dict[str, Any]: ...

    def rom(self, settings: Mapping[str, Any], randomization: Mapping[str, Any], rom: Path, out: Path) -> None: ...


class SubprocessEngine:
    def __init__(self, binary: Path, data_dir: Path, maps_dir: Optional[Path] = None):
        self.binary = Path(binary)
        self.data_dir = Path(data_dir)
        self.maps_dir = maps_dir

    def call(self, command: str, request: Mapping[str, Any]) -> Any:
        proc = subprocess.run([str(self.binary), "--data", str(self.data_dir.resolve()), command],
                              input=json.dumps(request).encode(), capture_output=True)
        # Map Rando prints progress to stdout: the response is the last line.
        lines = proc.stdout.strip().splitlines()
        try:
            response = json.loads(lines[-1])
        except (ValueError, IndexError):
            raise RuntimeError(f"smmr-engine {command} crashed (exit {proc.returncode}): "
                               f"{proc.stderr.decode(errors='replace')[-2000:]}") from None
        if "error" in response:
            raise EngineError(response["error"])
        return response["ok"]

    def info(self) -> Dict[str, Any]:
        return self.call("info", {})

    def upgrade(self, settings: Mapping[str, Any]) -> Dict[str, Any]:
        return self.call("upgrade", {"settings": settings})["settings"]

    def randomize(self, settings: Mapping[str, Any], seed: int) -> Dict[str, Any]:
        request: Dict[str, Any] = {"settings": settings, "seed": seed}
        if self.maps_dir is not None:
            request["maps_dir"] = str(Path(self.maps_dir).resolve())
        return self.call("randomize", request)

    def rom(self, settings: Mapping[str, Any], randomization: Mapping[str, Any], rom: Path, out: Path) -> None:
        self.call("rom", {"settings": settings, "randomization": randomization,
                          "rom": str(Path(rom).resolve()), "out": str(Path(out).resolve())})
