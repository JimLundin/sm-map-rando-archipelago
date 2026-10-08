"""A headless libretro frontend for ROM scenario tests: run frames, press buttons, read and write WRAM/SRAM.

    emu = Emulator(core_path, rom_bytes)
    emu.run(60)                         # frames
    emu.press("start", frames=2)
    emu.wram[0x0998]                    # game state (WRAM offset, i.e. $7E:0998)
    state = emu.save_state(); emu.load_state(state)

The core is a libretro SNES core (tested with snes9x); `SMMR_SNES_CORE` points to it.
"""
from __future__ import annotations

import ctypes as C
import os
from typing import Dict, Optional

BUTTONS = {"b": 0, "y": 1, "select": 2, "start": 3, "up": 4, "down": 5, "left": 6, "right": 7, "a": 8, "x": 9,
           "l": 10, "r": 11}
MEMORY_SAVE_RAM, MEMORY_SYSTEM_RAM = 0, 2
ENV_GET_CAN_DUPE, ENV_SET_PIXEL_FORMAT, ENV_GET_SYSTEM_DIRECTORY, ENV_GET_SAVE_DIRECTORY = 3, 10, 9, 31
ENV_GET_VARIABLE = 15

ENVIRONMENT = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VIDEO_REFRESH = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUDIO_SAMPLE = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
AUDIO_SAMPLE_BATCH = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
INPUT_POLL = C.CFUNCTYPE(None)
INPUT_STATE = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)


class GameInfo(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p), ("size", C.c_size_t), ("meta", C.c_char_p)]


class Memory:
    """A libretro memory region as a mutable byte view, with little-endian word helpers."""

    def __init__(self, pointer: int, size: int):
        self.view = (C.c_uint8 * size).from_address(pointer)

    def __getitem__(self, key):
        return bytes(self.view[key]) if isinstance(key, slice) else self.view[key]

    def __setitem__(self, offset: int, value: int) -> None:
        self.view[offset] = value

    def u16(self, offset: int) -> int:
        return self.view[offset] | self.view[offset + 1] << 8

    def write_u16(self, offset: int, value: int) -> None:
        self.view[offset], self.view[offset + 1] = value & 0xFF, value >> 8 & 0xFF

    def write(self, offset: int, data: bytes) -> None:
        for i, b in enumerate(data):
            self.view[offset + i] = b


class Emulator:
    def __init__(self, rom: bytes, core_path: Optional[str] = None):
        core_path = core_path or os.environ.get("SMMR_SNES_CORE", "/tmp/snes9x/libretro/snes9x_libretro.so")
        self.lib = C.CDLL(core_path)
        self.held: Dict[int, bool] = {}
        self.frame = 0
        # Keep the callbacks referenced: the core holds raw pointers to them.
        self._callbacks = [ENVIRONMENT(self._environment), VIDEO_REFRESH(lambda *a: None),
                           AUDIO_SAMPLE(lambda *a: None), AUDIO_SAMPLE_BATCH(lambda data, frames: frames),
                           INPUT_POLL(lambda: None), INPUT_STATE(self._input_state)]
        env, video, audio, audio_batch, poll, state = self._callbacks
        self.lib.retro_set_environment(env)
        self.lib.retro_init()
        self.lib.retro_set_video_refresh(video)
        self.lib.retro_set_audio_sample(audio)
        self.lib.retro_set_audio_sample_batch(audio_batch)
        self.lib.retro_set_input_poll(poll)
        self.lib.retro_set_input_state(state)
        self._rom = C.create_string_buffer(rom, len(rom))
        info = GameInfo(None, C.cast(self._rom, C.c_void_p), len(rom), None)
        if not self.lib.retro_load_game(C.byref(info)):
            raise RuntimeError("the core refused the ROM")
        self.lib.retro_get_memory_data.restype = C.c_void_p
        self.lib.retro_get_memory_size.restype = C.c_size_t
        self.wram = self._memory(MEMORY_SYSTEM_RAM)
        self.sram = self._memory(MEMORY_SAVE_RAM)

    def _memory(self, kind: int) -> Memory:
        return Memory(self.lib.retro_get_memory_data(kind), self.lib.retro_get_memory_size(kind))

    def _environment(self, cmd: int, data: int) -> bool:
        if cmd == ENV_SET_PIXEL_FORMAT:
            return True
        if cmd == ENV_GET_CAN_DUPE:
            C.cast(data, C.POINTER(C.c_bool))[0] = True
            return True
        return False

    def _input_state(self, port: int, device: int, index: int, button: int) -> int:
        return 1 if port == 0 and self.held.get(button) else 0

    def run(self, frames: int = 1) -> None:
        for _ in range(frames):
            self.lib.retro_run()
            self.frame += 1

    def hold(self, *buttons: str) -> None:
        self.held = {BUTTONS[b]: True for b in buttons}

    def press(self, *buttons: str, frames: int = 2, release: int = 2) -> None:
        self.hold(*buttons)
        self.run(frames)
        self.hold()
        self.run(release)

    def save_state(self) -> bytes:
        self.lib.retro_serialize_size.restype = C.c_size_t
        size = self.lib.retro_serialize_size()
        buffer = C.create_string_buffer(size)
        if not self.lib.retro_serialize(buffer, C.c_size_t(size)):
            raise RuntimeError("serialize failed")
        return buffer.raw

    def load_state(self, state: bytes) -> None:
        buffer = C.create_string_buffer(state, len(state))
        if not self.lib.retro_unserialize(buffer, C.c_size_t(len(state))):
            raise RuntimeError("unserialize failed")

    def close(self) -> None:
        self.lib.retro_unload_game()
        self.lib.retro_deinit()
