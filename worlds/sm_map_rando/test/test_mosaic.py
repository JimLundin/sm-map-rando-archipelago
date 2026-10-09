"""
Getting the Mosaic tile theme patches into the data directory, with the download and the native decompression
replaced by local stand-ins. A patch file opened twice starts two clients, which then run this at the same time.
"""
import io
import os
import shutil
import tarfile
import tempfile
import unittest
from typing import Callable, Optional
from unittest import mock

from .. import native

BUILD_ID = "test-build"
PATCHES = {"tilesets.bps": b"tilesets", "Base-79804-0.bps": b"room"}


def make_archive(path: str) -> None:
    """A Mosaic archive as Map Rando publishes it (flat, with a "." entry), uncompressed: see FakeModule."""
    with tarfile.open(path, "w") as tf:
        tf.add(tempfile.mkdtemp(), arcname=".")
        for name, data in PATCHES.items():
            info = tarfile.TarInfo(f"./{name}")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


class FakeModule:
    """Stands in for pysmmaprando: the test archive isn't compressed, so decompressing is copying."""
    def __init__(self):
        self.during_decompress: Optional[Callable[[], None]] = None

    def zstd_decompress_file(self, src: str, dst: str) -> None:
        shutil.copyfile(src, dst)
        if self.during_decompress is not None:
            during, self.during_decompress = self.during_decompress, None
            during()


class TestMosaicPatches(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.data = os.path.join(self.root, "data")
        self.cache = os.path.join(self.root, "cache")
        self.dest = os.path.join(self.data, "patches", "mosaic")
        os.makedirs(os.path.join(self.data, "patches", "ips"))
        self.module = FakeModule()
        self.downloads = 0

        def download(url: str, dest: str) -> None:
            self.downloads += 1
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            make_archive(dest)

        for target, value in [("data_root", lambda: self.data), ("mosaic_build_id", lambda: BUILD_ID),
                              ("get_module", lambda: self.module), ("download", download)]:
            patcher = mock.patch.object(native, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(native.Utils, "cache_path", lambda *p: os.path.join(self.cache, *p))
        patcher.start()
        self.addCleanup(patcher.stop)

    def assert_patches_in_place(self):
        for name, data in PATCHES.items():
            with open(os.path.join(self.dest, name), "rb") as f:
                self.assertEqual(f.read(), data)

    def test_fresh(self):
        native.ensure_mosaic_patches()
        self.assert_patches_in_place()
        native.ensure_mosaic_patches()
        self.assertEqual(self.downloads, 1)

    def test_partial_copy_is_redone(self):
        # an earlier run was interrupted while copying the patches: tilesets.bps never made it
        os.makedirs(self.dest)
        open(os.path.join(self.dest, "Base-79804-0.bps"), "wb").close()
        native.ensure_mosaic_patches()
        self.assert_patches_in_place()

    def test_other_run_finishes_meanwhile(self):
        # a second client finishes all the steps while this one is decompressing
        self.module.during_decompress = native.ensure_mosaic_patches
        native.ensure_mosaic_patches()
        self.assert_patches_in_place()
        leftovers = [n for n in os.listdir(os.path.join(self.cache, "sm_map_rando", "mosaic", BUILD_ID))
                     if n not in ("patches", f"Mosaic-{BUILD_ID}.tar.zstd")]
        self.assertEqual(leftovers, [])
