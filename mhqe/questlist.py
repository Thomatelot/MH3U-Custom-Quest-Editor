"""The game's list of base-game quests: ``romfs/quest/<eu|us>/quest.list``, also stored in
``quest00.arc`` as ``quest\\<eu|us>\\quest``. The game only loads the quests this list names, so a
new Village / Port quest must be added to it as well as to the archive.

The file is an MT Framework XFS object file (3 class definitions, then the objects). Layout found
by a tester who added quest 1120 by hand (it then appeared in the game) and checked here on the
EU and US files, which are identical:

    0x008  u32  number of objects (the root, the array, one per quest)
    0x130  root object:  u16 1, u16 id 0, u32 size (from 0x134 to the end of the file)
    0x144  array object: u16 3, u16 id 1, u32 size (from 0x148 to the end), ..., u32 count at 0x151
    0x155  one 16-byte object per quest:
           u16 5 (class), u16 object id (2, 3...), u32 12, u32 1, u32 quest number

New quests are appended after the last one, as in the tested file.
"""
from __future__ import annotations

import struct

MAGIC = b"XFS\0"
COUNT_OFF, ROOT_SIZE_OFF, ARRAY_SIZE_OFF, ARRAY_COUNT_OFF, FIRST = 0x08, 0x134, 0x148, 0x151, 0x155
REC = 16
TYPE_HASH = 0x7284DAF5              # the archive's type for this file


class QuestListError(ValueError):
    """The file does not have the layout this module knows."""


def _check(data: bytes) -> int:
    if data[:4] != MAGIC or len(data) < FIRST:
        raise QuestListError("not a quest.list file")
    (n,) = struct.unpack_from("<I", data, ARRAY_COUNT_OFF)
    ok = (len(data) == FIRST + n * REC
          and struct.unpack_from("<I", data, COUNT_OFF)[0] == n + 2
          and struct.unpack_from("<I", data, ROOT_SIZE_OFF)[0] == len(data) - ROOT_SIZE_OFF
          and struct.unpack_from("<I", data, ARRAY_SIZE_OFF)[0] == len(data) - ARRAY_SIZE_OFF)
    if not ok:
        raise QuestListError("quest.list has an unexpected layout")
    for i in range(n):
        cls, oid, size, one, _no = struct.unpack_from("<HHIII", data, FIRST + i * REC)
        if (cls, oid, size, one) != (5, i + 2, 12, 1):
            raise QuestListError(f"quest.list: unexpected record {i}")
    return n


def numbers(data: bytes) -> list[int]:
    """Quest numbers in the order of the file."""
    n = _check(data)
    return [struct.unpack_from("<I", data, FIRST + i * REC + 12)[0] for i in range(n)]


def add(data: bytes, new_numbers) -> bytes:
    """The list with these quest numbers appended (numbers already listed are skipped)."""
    n = _check(data)
    have = set(numbers(data))
    extra = [no for no in dict.fromkeys(int(x) for x in new_numbers) if no not in have]
    if not extra:
        return bytes(data)
    out = bytearray(data)
    for k, no in enumerate(extra):
        out += struct.pack("<HHIII", 5, n + 2 + k, 12, 1, no)
    total = n + len(extra)
    struct.pack_into("<I", out, COUNT_OFF, total + 2)
    struct.pack_into("<I", out, ROOT_SIZE_OFF, len(out) - ROOT_SIZE_OFF)
    struct.pack_into("<I", out, ARRAY_SIZE_OFF, len(out) - ARRAY_SIZE_OFF)
    struct.pack_into("<I", out, ARRAY_COUNT_OFF, total)
    _check(bytes(out))
    return bytes(out)
