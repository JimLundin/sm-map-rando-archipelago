"""
Minimal headless libretro frontend (for the snes9x libretro core), used to smoke-test generated ROMs: boot the game,
navigate to gameplay, and exercise the Archipelago receive queue the way the SNI client does.
"""
import ctypes as C

RETRO_MEMORY_SAVE_RAM = 0
RETRO_MEMORY_SYSTEM_RAM = 2
RETRO_ENVIRONMENT_GET_CAN_DUPE = 3
RETRO_ENVIRONMENT_SET_PIXEL_FORMAT = 10

JOYPAD = {"B": 0, "Y": 1, "Select": 2, "Start": 3, "Up": 4, "Down": 5, "Left": 6, "Right": 7, "A": 8, "X": 9,
          "L": 10, "R": 11}


class GameInfo(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p), ("size", C.c_size_t), ("meta", C.c_char_p)]


ENV_CB = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VIDEO_CB = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUDIO_CB = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
AUDIO_BATCH_CB = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
POLL_CB = C.CFUNCTYPE(None)
STATE_CB = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)


class Emulator:
    def __init__(self, core_path: str, rom: bytes):
        self.lib = C.CDLL(core_path)
        self.pressed = set()
        self.frame = 0
        self.pixel_format = 0
        self.last_frame = None
        self._cbs = [ENV_CB(self._env), VIDEO_CB(self._video), AUDIO_CB(lambda *a: None),
                     AUDIO_BATCH_CB(lambda d, n: n), POLL_CB(lambda: None), STATE_CB(self._input)]
        self.lib.retro_set_environment(self._cbs[0])
        self.lib.retro_set_video_refresh(self._cbs[1])
        self.lib.retro_set_audio_sample(self._cbs[2])
        self.lib.retro_set_audio_sample_batch(self._cbs[3])
        self.lib.retro_set_input_poll(self._cbs[4])
        self.lib.retro_set_input_state(self._cbs[5])
        self.lib.retro_init()
        self._rom = C.create_string_buffer(rom, len(rom))
        info = GameInfo(None, C.cast(self._rom, C.c_void_p), len(rom), None)
        if not self.lib.retro_load_game(C.byref(info)):
            raise RuntimeError("retro_load_game failed")
        self.lib.retro_get_memory_data.restype = C.c_void_p
        self.lib.retro_get_memory_size.restype = C.c_size_t

    def _video(self, data, width, height, pitch):
        if data:
            self.last_frame = (C.string_at(data, pitch * height), width, height, pitch)

    def screenshot(self, path):
        """Save the last video frame as a PNG (requires Pillow)."""
        from PIL import Image
        raw, width, height, pitch = self.last_frame
        img = Image.new("RGB", (width, height))
        px = img.load()
        for y in range(height):
            for x in range(width):
                if self.pixel_format == 1:  # XRGB8888
                    b, g, r = raw[y * pitch + 4 * x:y * pitch + 4 * x + 3]
                else:
                    v = raw[y * pitch + 2 * x] | (raw[y * pitch + 2 * x + 1] << 8)
                    if self.pixel_format == 2:  # RGB565
                        r, g, b = (v >> 11) << 3, ((v >> 5) & 0x3F) << 2, (v & 0x1F) << 3
                    else:  # 0RGB1555
                        r, g, b = ((v >> 10) & 0x1F) << 3, ((v >> 5) & 0x1F) << 3, (v & 0x1F) << 3
                px[x, y] = (r, g, b)
        img.save(path)

    def _env(self, cmd, data):
        if cmd == RETRO_ENVIRONMENT_SET_PIXEL_FORMAT:
            self.pixel_format = C.cast(data, C.POINTER(C.c_uint))[0]
            return True
        if cmd == RETRO_ENVIRONMENT_GET_CAN_DUPE:
            C.cast(data, C.POINTER(C.c_bool))[0] = True
            return True
        return False

    def _input(self, port, device, index, button):
        if port == 0 and device == 1:
            return 1 if button in self.pressed else 0
        return 0

    def _memory(self, kind):
        ptr = self.lib.retro_get_memory_data(kind)
        size = self.lib.retro_get_memory_size(kind)
        return (C.c_ubyte * size).from_address(ptr)

    @property
    def wram(self):
        return self._memory(RETRO_MEMORY_SYSTEM_RAM)

    @property
    def sram(self):
        return self._memory(RETRO_MEMORY_SAVE_RAM)

    def read16(self, mem, addr):
        return mem[addr] | (mem[addr + 1] << 8)

    def write(self, mem, addr, data: bytes):
        for i, b in enumerate(data):
            mem[addr + i] = b

    def run(self, frames=1, buttons=()):
        self.pressed = {JOYPAD[b] for b in buttons}
        for _ in range(frames):
            self.lib.retro_run()
            self.frame += 1
        self.pressed = set()

    def game_mode(self):
        return self.read16(self.wram, 0x0998)
