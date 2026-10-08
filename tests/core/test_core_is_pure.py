"""`core` must not depend on Archipelago, so that its tests run in plain pytest in seconds."""
import ast
from pathlib import Path

CORE = Path(__file__).resolve().parents[2] / "world" / "smmr" / "core"
ALLOWED_TOP_LEVEL = {"__future__", "collections", "copy", "dataclasses", "functools", "json", "pathlib", "struct",
                     "subprocess", "typing", "itertools", "enum", "hashlib", "zlib", "random", "tomllib", "platform", "sys"}


def test_core_only_imports_the_standard_library_and_itself():
    for path in CORE.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert name.split(".")[0] in ALLOWED_TOP_LEVEL, f"{path.name} imports {name}"
