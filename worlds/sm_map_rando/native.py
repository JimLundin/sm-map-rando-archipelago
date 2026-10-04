"""
Access to the native Map Rando library (pysmmaprando) and to the Map Rando data files.

The randomizer itself is the upstream Map Rando Rust code (https://github.com/blkerby/MapRandomizer), compiled
as a Python extension module. Since Python cannot import extension modules from inside a zip file (.apworld),
the wheel for the current platform is bundled in the world and extracted to the Archipelago cache directory on
first use, together with the game data that the randomizer reads from disk.
"""
from __future__ import annotations

import glob
import hashlib
import io
import json
import logging
import os
import platform
import shutil
import sys
import tarfile
import tempfile
import threading
import urllib.request
import zipfile
from typing import Any, Dict, Optional

import Utils

logger = logging.getLogger("Super Metroid Map Rando")

from .version import WORLD_VERSION as PYSMMAPRANDO_VERSION  # the native module has the world's version
GAME_DATA_DIR = "maprando"  # directory within the world's data directory
UPSTREAM_COMMIT_FILE = "upstream_commit.txt"

_lock = threading.RLock()
_module = None
_instance = None


def world_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def apworld_path() -> Optional[str]:
    """Path of the .apworld file this world was loaded from, or None if loaded from a directory."""
    path = world_dir()
    marker = ".apworld"
    if marker in path:
        return path[:path.index(marker) + len(marker)]
    return None


def cache_root() -> str:
    return Utils.cache_path("sm_map_rando", PYSMMAPRANDO_VERSION)


def _content_id() -> str:
    """Identifier of the world contents, so that a changed .apworld gets freshly extracted data."""
    ap = apworld_path()
    if ap is None:
        return "dev"
    st = os.stat(ap)
    return hashlib.sha1(f"{ap}:{st.st_size}:{st.st_mtime_ns}".encode()).hexdigest()[:16]


def _extract_from_apworld(member_prefix: str, dest: str) -> None:
    ap = apworld_path()
    assert ap is not None
    tmp = dest + ".tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(ap) as zf:
        for name in zf.namelist():
            if name.startswith(member_prefix) and not name.endswith("/"):
                rel = name[len(member_prefix):]
                target = os.path.join(tmp, *rel.split("/"))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    shutil.rmtree(dest, ignore_errors=True)
    os.replace(tmp, dest)


def data_root() -> str:
    """Directory laid out like the MapRandomizer repository, containing the data read by the randomizer."""
    with _lock:
        local = os.path.join(world_dir(), "data", GAME_DATA_DIR)
        if apworld_path() is None:
            return local
        dest = os.path.join(cache_root(), "data-" + _content_id())
        if not os.path.isdir(dest):
            logger.info("Extracting Map Rando data to %s", dest)
            world_folder = os.path.basename(world_dir())
            _extract_from_apworld(f"{world_folder}/data/{GAME_DATA_DIR}/", dest)
        return dest


def download(url: str, dest: str) -> None:
    """Download a file atomically (used for map pools, sprites and Mosaic tile theme patches)."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(dest), suffix=".part")
    try:
        with os.fdopen(fd, "wb") as f, urllib.request.urlopen(url, timeout=120) as response:
            shutil.copyfileobj(response, f)
        os.replace(tmp, dest)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _wheel_platform_tags() -> list:
    machine = platform.machine().lower()
    if sys.platform.startswith("win"):
        return ["win_amd64"] if machine in ("amd64", "x86_64") else ["win_arm64"]
    if sys.platform.startswith("linux"):
        return ["x86_64"] if machine in ("x86_64", "amd64") else ["aarch64"]
    if sys.platform == "darwin":
        return ["universal2", "arm64" if machine == "arm64" else "x86_64"]
    return []


def _find_bundled_wheel() -> Optional[str]:
    """Return the name of the bundled wheel for this platform (as a path or zip member name)."""
    tags = _wheel_platform_tags()
    ap = apworld_path()
    if ap is None:
        names = [os.path.basename(p) for p in glob.glob(os.path.join(world_dir(), "lib", "*.whl"))]
    else:
        with zipfile.ZipFile(ap) as zf:
            names = [n.split("/")[-1] for n in zf.namelist() if n.endswith(".whl") and "/lib/" in n]
    for tag in tags:
        for name in names:
            if f"pysmmaprando-{PYSMMAPRANDO_VERSION}-" in name and tag in name:
                return name
    return None


def _install_bundled_wheel() -> bool:
    wheel = _find_bundled_wheel()
    if wheel is None:
        return False
    dest = os.path.join(cache_root(), "lib-" + _content_id())
    if not os.path.isdir(os.path.join(dest, "pysmmaprando")):
        logger.info("Installing bundled %s to %s", wheel, dest)
        ap = apworld_path()
        if ap is None:
            data = open(os.path.join(world_dir(), "lib", wheel), "rb").read()
        else:
            world_folder = os.path.basename(world_dir())
            with zipfile.ZipFile(ap) as zf:
                data = zf.read(f"{world_folder}/lib/{wheel}")
        tmp = dest + ".tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(io.BytesIO(data)) as wf:
            wf.extractall(tmp)
        shutil.rmtree(dest, ignore_errors=True)
        os.replace(tmp, dest)
    if dest not in sys.path:
        sys.path.insert(0, dest)
    return True


def get_module():
    """Import the native module, installing the bundled wheel if needed."""
    global _module
    with _lock:
        if _module is not None:
            return _module
        try:
            import pysmmaprando  # installed in the Python environment (e.g. from source)
            if getattr(pysmmaprando, "VERSION", None) != PYSMMAPRANDO_VERSION:
                raise ImportError(f"pysmmaprando {getattr(pysmmaprando, 'VERSION', '?')} found, "
                                  f"{PYSMMAPRANDO_VERSION} required")
        except ImportError as e:
            sys.modules.pop("pysmmaprando", None)
            if not _install_bundled_wheel():
                raise RuntimeError(
                    f"Super Metroid Map Rando requires the native module pysmmaprando {PYSMMAPRANDO_VERSION}, "
                    f"which is not bundled for this platform ({sys.platform} {platform.machine()}). "
                    f"It can be built from source with maturin (see the world's setup guide).") from e
            import pysmmaprando
        level = os.getenv("SMMAPRANDO_LOG", "error")
        pysmmaprando.init_logging(level)
        _module = pysmmaprando
        return _module


def get_map_rando():
    """The (lazily loaded) native randomizer instance with game data loaded."""
    global _instance
    with _lock:
        if _instance is None:
            module = get_module()
            maps_cache = os.path.join(Utils.cache_path("sm_map_rando"), "maps")
            _instance = module.MapRando(data_root(), maps_cache, download)
        return _instance


# Upstream repository files fetched on demand, rather than bundled, to keep the world small.

def upstream_commit() -> str:
    path = os.path.join(world_dir(), "data", UPSTREAM_COMMIT_FILE)
    ap = apworld_path()
    if ap is None:
        return open(path).read().strip()
    with zipfile.ZipFile(ap) as zf:
        return zf.read(f"{os.path.basename(world_dir())}/data/{UPSTREAM_COMMIT_FILE}").decode().strip()


def ensure_samus_sprite(name: str) -> None:
    """Make sure the Samus sprite patch is available in the data directory (downloading if necessary)."""
    if not name.replace("_", "").replace("-", "").isalnum():
        raise ValueError(f"Invalid Samus sprite name: {name}")
    dest = os.path.join(data_root(), "patches", "samus_sprites", f"{name}.ips")
    if os.path.exists(dest):
        return
    cached = os.path.join(Utils.cache_path("sm_map_rando"), "samus_sprites", upstream_commit(), f"{name}.ips")
    if not os.path.exists(cached):
        url = (f"https://raw.githubusercontent.com/blkerby/MapRandomizer/{upstream_commit()}"
               f"/patches/samus_sprites/{name}.ips")
        logger.info("Downloading Samus sprite %s", url)
        download(url, cached)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(cached, dest)


def mosaic_build_id() -> str:
    path = os.path.join(world_dir(), "data", "MOSAIC_BUILD_ID")
    ap = apworld_path()
    if ap is None:
        return open(path).read().strip()
    with zipfile.ZipFile(ap) as zf:
        return zf.read(f"{os.path.basename(world_dir())}/data/MOSAIC_BUILD_ID").decode().strip()


def ensure_mosaic_patches() -> None:
    """Make sure the Mosaic tile theme patches are available (downloading them if necessary)."""
    dest = os.path.join(data_root(), "patches", "mosaic")
    if os.path.isdir(dest) and os.listdir(dest):
        return
    build_id = mosaic_build_id()
    archive_dir = os.path.join(Utils.cache_path("sm_map_rando"), "mosaic", build_id)
    extracted = os.path.join(archive_dir, "patches")
    if not os.path.isdir(extracted):
        archive = os.path.join(archive_dir, f"Mosaic-{build_id}.tar.zstd")
        if not os.path.exists(archive):
            url = f"https://map-rando-artifacts.s3.us-west-004.backblazeb2.com/Mosaic/Mosaic-{build_id}.tar.zstd"
            logger.info("Downloading Mosaic tile theme patches from %s", url)
            download(url, archive)
        tar_path = archive[:-len(".zstd")]
        get_module().zstd_decompress_file(archive, tar_path)
        tmp = extracted + ".tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        with tarfile.open(tar_path) as tf:
            tf.extractall(tmp, filter="data")
        os.remove(tar_path)
        os.replace(tmp, extracted)
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(extracted, dest)


def randomize(settings: Dict[str, Any], random_seed: int, **kwargs) -> Dict[str, Any]:
    return json.loads(get_map_rando().randomize(json.dumps(settings), random_seed, **kwargs))


def upgrade_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    return json.loads(get_map_rando().upgrade_settings(json.dumps(settings)))
