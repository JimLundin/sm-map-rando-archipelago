import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "world" / "smmr"))   # `core` alone: importing `smmr` needs Archipelago

from core.catalog import Catalog  # noqa: E402


def load_json(relative: str):
    return json.loads((ROOT / relative).read_text())


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return Catalog.from_info(load_json("world/smmr/data/info.json"))


@pytest.fixture(scope="session")
def seed():
    return load_json("fixtures/seeds/default-vanilla-1.json")
