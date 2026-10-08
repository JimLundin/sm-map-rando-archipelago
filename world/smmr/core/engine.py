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
from typing import IO, Any, Dict, Mapping, Optional, Protocol

RESPONSE = b"\x1e"


def platform_tag() -> str:
    """Names the engine build for this machine in the .apworld's bin/ (e.g. linux-x86_64, win32-amd64)."""
    return f"{sys.platform}-{platform.machine().lower()}"


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
        self._process: Optional[subprocess.Popen] = None
        self._stderr: Optional[IO[bytes]] = None
        self._lock = threading.Lock()

    def _start(self) -> subprocess.Popen:
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
