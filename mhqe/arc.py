"""MT Framework ARC container, 3DS (little-endian) variant, as used by
``romfs/arc/quest/eu/quest00.arc``.

    header   'ARC\\0' u16 version(0x10) u16 count u32 0            (12 bytes)
    entry    char[64] path | u32 type_hash | u32 compressed_size |
             u32 (flags << 29 | uncompressed_size) | u32 offset    (80 bytes)
    data     zlib streams; the first starts at the first 0x8000 boundary after
             the entry table, the others follow back to back.

Verified on the EU 3DS quest00.arc: all 366 entries decompress and match the
loose files in romfs/quest/eu byte for byte.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

MAGIC = b"ARC\0"
HEADER_SIZE = 12
ENTRY_SIZE = 80
DATA_ALIGN = 0x8000
DEFAULT_FLAGS = 2
SIZE_MASK = 0x1FFFFFFF


class ArcError(ValueError):
    pass


@dataclass
class ArcEntry:
    path: str                      # e.g. 'quest\\eu\\q_02906'
    type_hash: int
    flags: int
    data: bytes                    # decompressed payload

    @property
    def leaf(self) -> str:
        return self.path.replace("\\", "/").rsplit("/", 1)[-1]


@dataclass
class Arc:
    version: int = 0x10
    entries: list[ArcEntry] = field(default_factory=list)

    def find(self, path: str) -> int | None:
        for i, e in enumerate(self.entries):
            if e.path == path:
                return i
        return None


def parse(raw: bytes) -> Arc:
    if raw[:4] != MAGIC:
        raise ArcError(f"not an ARC archive (magic {raw[:4]!r})")
    version, count = struct.unpack_from("<HH", raw, 4)
    if HEADER_SIZE + count * ENTRY_SIZE > len(raw):
        raise ArcError("archive is truncated")
    arc = Arc(version)
    for i in range(count):
        off = HEADER_SIZE + i * ENTRY_SIZE
        name = raw[off:off + 64].split(b"\0", 1)[0].decode("ascii", "replace")
        type_hash, csize, dsize_flags, data_off = struct.unpack_from("<IIII", raw, off + 64)
        try:
            data = zlib.decompress(raw[data_off:data_off + csize])
        except zlib.error as exc:
            raise ArcError(f"entry {i} ({name}) is not a valid zlib stream: {exc}") from None
        if len(data) != dsize_flags & SIZE_MASK:
            raise ArcError(f"entry {i} ({name}) has an unexpected size")
        arc.entries.append(ArcEntry(name, type_hash, dsize_flags >> 29, data))
    return arc


def read(path: str | Path) -> Arc:
    return parse(Path(path).read_bytes())


def build(arc: Arc, level: int = 6) -> bytes:
    """Serialize an archive (zlib level 6 = what the original files use)."""
    count = len(arc.entries)
    blobs = [zlib.compress(e.data, level) for e in arc.entries]
    table_end = HEADER_SIZE + count * ENTRY_SIZE
    off = (table_end + DATA_ALIGN - 1) // DATA_ALIGN * DATA_ALIGN
    offsets = []
    for blob in blobs:
        offsets.append(off)
        off += len(blob)
    buf = bytearray(off)
    struct.pack_into("<4sHHI", buf, 0, MAGIC, arc.version, count, 0)
    for i, (e, blob, data_off) in enumerate(zip(arc.entries, blobs, offsets)):
        name = e.path.encode("ascii")
        if len(name) >= 64:
            raise ArcError(f"entry path too long: {e.path!r}")
        eo = HEADER_SIZE + i * ENTRY_SIZE
        buf[eo:eo + 64] = name + bytes(64 - len(name))
        struct.pack_into("<IIII", buf, eo + 64, e.type_hash, len(blob),
                         (e.flags << 29) | len(e.data), data_off)
        buf[data_off:data_off + len(blob)] = blob
    return bytes(buf)
