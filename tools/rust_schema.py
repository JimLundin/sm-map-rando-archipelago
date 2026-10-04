"""
Read the structure of Map Rando's settings from its Rust source (rust/maprando/src/settings.rs): the fields of each
struct with their types, and the variants of each enum (with serde renames). This is the authoritative definition of
the settings JSON, so the Archipelago options are generated from it.
"""
import os
import re
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_RS = os.path.join(ROOT, "MapRandomizer", "rust", "maprando", "src", "settings.rs")

ITEM_TYPES = {"Item"}
INT_TYPES = {"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64", "usize", "isize"}
FLOAT_TYPES = {"f32", "f64"}


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def _blocks(src: str, keyword: str):
    """Yield (name, body) for each `pub <keyword> Name { ... }` (brace-matched)."""
    for m in re.finditer(rf"pub\s+{keyword}\s+(\w+)\s*\{{", src):
        depth, i = 1, m.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(src[i], 0)
            i += 1
        yield m.group(1), src[m.end():i - 1]


def parse(path: str = SETTINGS_RS) -> Tuple[Dict[str, List[Tuple[str, str]]], Dict[str, List[str]]]:
    src = _strip_comments(open(path, encoding="utf-8").read())
    structs: Dict[str, List[Tuple[str, str]]] = {}
    for name, body in _blocks(src, "struct"):
        fields = []
        for fm in re.finditer(r"pub\s+(\w+)\s*:\s*([^,]+(?:<[^>]*>)?[^,]*),", body + ","):
            fields.append((fm.group(1), re.sub(r"\s+", "", fm.group(2))))
        structs[name] = fields
    enums: Dict[str, List[str]] = {}
    for name, body in _blocks(src, "enum"):
        variants = []
        rename: Optional[str] = None
        for token in re.finditer(r'#\[serde\(rename\s*=\s*"([^"]+)"\)\]|#\[[^\]]*\]|(\w+)\s*(?:=\s*[^,]+)?\s*(?:,|$)',
                                 body):
            if token.group(1):
                rename = token.group(1)
            elif token.group(2):
                variants.append(rename or token.group(2))
                rename = None
        enums[name] = variants
    return structs, enums


def leaf_settings(structs, enums, root: str = "RandomizerSettings", prefix: str = ""):
    """Yield (path, kind, detail) for every leaf of the settings JSON:
    kind is one of bool, int, float, string, enum (detail = list of values), option (detail = inner type),
    list (detail = element type)."""
    for field, typ in structs[root]:
        path = prefix + field
        inner = typ
        optional = False
        m = re.fullmatch(r"Option<(.+)>", typ)
        if m:
            inner, optional = m.group(1), True
        if inner in structs:
            yield from leaf_settings(structs, enums, inner, path + ".")
        elif inner == "bool":
            yield path, "bool", optional
        elif inner in INT_TYPES:
            yield path, "int", optional
        elif inner in FLOAT_TYPES:
            yield path, "float", optional
        elif inner == "String":
            yield path, "string", optional
        elif inner in enums:
            yield path, "enum", enums[inner]
        elif inner.startswith("Vec<"):
            yield path, "list", inner[4:-1]
        else:
            yield path, "other", inner


if __name__ == "__main__":
    s, e = parse()
    for leaf in leaf_settings(s, e):
        print(*leaf)
