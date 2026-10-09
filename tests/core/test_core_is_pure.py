"""`core` must not depend on Archipelago, so that its tests run in plain pytest in seconds."""
import ast
from pathlib import Path

CORE = Path(__file__).resolve().parents[2] / "world" / "smmr" / "core"
ALLOWED_TOP_LEVEL = {"__future__", "collections", "copy", "dataclasses", "functools", "json", "pathlib", "struct",
                     "subprocess", "tempfile", "threading", "typing", "itertools", "enum", "hashlib", "zlib", "random", "re", "tomllib", "platform", "sys",
                     "unicodedata", "types"}


def type_checking_only(tree: ast.Module) -> set[ast.AST]:
    """The nodes under `if TYPE_CHECKING:`: imports for the type checker, never run."""
    return {node for block in ast.walk(tree)
            if isinstance(block, ast.If) and isinstance(block.test, ast.Name) and block.test.id == "TYPE_CHECKING"
            for stmt in block.body for node in ast.walk(stmt)}


def test_core_only_imports_the_standard_library_and_itself() -> None:
    for path in CORE.glob("*.py"):
        tree = ast.parse(path.read_text())
        skipped = type_checking_only(tree)
        for node in ast.walk(tree):
            if node in skipped:
                continue
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert name.split(".")[0] in ALLOWED_TOP_LEVEL, f"{path.name} imports {name}"
