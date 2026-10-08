"""IPS patches: encode the bytes a patch writes, and apply them."""
from __future__ import annotations

from typing import Dict, Iterator, Tuple

HEADER, FOOTER = b"PATCH", b"EOF"
EOF_OFFSET = 0x454F46   # an offset spelling "EOF" can't start a record


def _runs(writes: Dict[int, int]) -> Iterator[Tuple[int, bytes]]:
    run_start, run = None, bytearray()
    for offset in sorted(writes):
        if run_start is not None and offset == run_start + len(run) and len(run) < 0xFFFF:
            run.append(writes[offset])
            continue
        if run_start is not None:
            yield run_start, bytes(run)
        run_start, run = offset, bytearray([writes[offset]])
    if run_start is not None:
        yield run_start, bytes(run)


def encode(writes: Dict[int, int]) -> bytes:
    out = bytearray(HEADER)
    for offset, data in _runs(writes):
        if offset == EOF_OFFSET:
            raise ValueError("a patch write at offset 0x454F46 isn't representable; move the code")
        if offset >= 1 << 24:
            raise ValueError(f"offset {offset:#x} is beyond IPS's 16 MiB")
        out += offset.to_bytes(3, "big") + len(data).to_bytes(2, "big") + data
    return bytes(out + FOOTER)


def apply(patch: bytes, rom: bytearray) -> None:
    if not patch.startswith(HEADER):
        raise ValueError("not an IPS patch")
    i = len(HEADER)
    while patch[i:i + 3] != FOOTER:
        offset = int.from_bytes(patch[i:i + 3], "big")
        size = int.from_bytes(patch[i + 3:i + 5], "big")
        i += 5
        if size == 0:   # RLE record
            count = int.from_bytes(patch[i:i + 2], "big")
            rom[offset:offset + count] = patch[i + 2:i + 3] * count
            i += 3
        else:
            rom[offset:offset + size] = patch[i:i + size]
            i += size
