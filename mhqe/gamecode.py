"""Tables of the game's program (exefs/code.bin) that quests point into.

All of them are found by their content, so the same code works on the EU and US versions (the
tables are byte-identical in both). Read from the game's code (addresses of the EU/US 1.0 code.bin,
virtual address = file offset + 0x100000):

* MASTER QUEST LIST (file offset 0xB43370): 504 quest numbers (u16), 0 = unused slot, 0xFFFF ends
  the list. A quest's position in this list is the number of its "cleared" bit in the save
  (function 0x9988D0 turns a quest number into that position, 0x99B62C reads the bit, 0x99B73C sets
  it). A quest that is not in the list can be played but is never recorded as cleared.

* ROAMING-MONSTER LISTS (pointers at 0xB27900, lists from 0xB233F8): the quest field
  nora_set_table is an index into the pointer table (0 and the empty slots mean "no list"). A list
  is a run of 30-byte entries closed by an all-zero entry; an entry is 15 u16:
      species, health, attack, defence, size %, ?, size spread, 0, ?, ?, chance %, 0,
      zenny, HR points, level
  (function 0x62B724 keeps the entries whose "level" is not above a value taken from the hunters,
  then draws one by its chance).

* START RECORDS (see monsterpack): byte 11 of a 56-byte start record is a "form" number the game
  hands to the monster when it appears (function 0x5C6DEC). It is 0 except in 13 records of
  Brachydios, Zinogre and Stygian Zinogre, the ones used by 'Clashing Fists!', 'Descent into
  Hades' and a few G rank quests.

* QUEST MAP -> STAGE (file offset 0xAEAEEE, 16 x 2 bytes): the quest field 'map' indexes it; byte 0
  is the stage the game loads (stage\\m01 ... m14; 26 = Moga Village, 27 = Port Tanzia, loaded by
  the same code, function 0x646770, for the hubs), byte 1 another stage for the same map (night
  versions m15 ... m25). Function 0x62B714 reads it. Right after it (0xAEAF0E, 18 bytes): quest
  map -> number of the map in the monster placement tables (see monsterpack). Map 9 is never used
  by the game's quests: it loads the Arena with the placement of the event Water Arena.
"""
from __future__ import annotations

import struct

BASE = 0x100000
MASTER_HEAD = struct.pack("<8H", 1101, 1102, 1103, 1104, 1105, 1106, 1201, 2201)
MASTER_MAX = 512                                   # the save holds 512 "cleared" bits
ROAM_ENTRY = 30
ROAM_FIELDS = ("em", "hp", "attack", "defence", "size", "f5", "size_spread", "f7", "f8", "f9",
               "chance", "f11", "zenny", "points", "level")
ROAM_HEAD = struct.pack("<5H", 12, 10, 7, 3, 100)   # the first list: a Great Jaggi
ROAM_SLOTS = 256                                    # the quest's list number is one byte


class CodeError(ValueError):
    pass


# ------------------------------------------------------------- master quest list
def find_master_list(code: bytes) -> tuple[int, list[int]]:
    """(file offset, quest numbers) of the list of quests that can be marked as cleared."""
    off = code.find(MASTER_HEAD)
    if off < 0 or code.find(MASTER_HEAD, off + 1) >= 0:
        raise CodeError("The game's quest list was not found in code.bin (unknown game version?).")
    out = []
    while len(out) <= MASTER_MAX:
        (v,) = struct.unpack_from("<H", code, off + 2 * len(out))
        if v == 0xFFFF:
            return off, out
        out.append(v)
    raise CodeError("The game's quest list has no end mark.")


def free_master_slots(numbers: list[int]) -> list[int]:
    """Unused positions, the ones of the longest unused run first (the block the game keeps for
    event quests it never got), so a new quest does not land between two quests of the same rank."""
    runs, i = [], 0
    while i < len(numbers):
        if numbers[i] == 0:
            j = i
            while j < len(numbers) and numbers[j] == 0:
                j += 1
            runs.append(list(range(i, j)))
            i = j
        else:
            i += 1
    runs.sort(key=lambda r: (-len(r), r[0]))
    return [i for r in runs for i in r if i < MASTER_MAX]


def register_quests(code: bytes, numbers) -> tuple[list[tuple[int, bytes]], dict[int, int]]:
    """IPS records that write the new quest numbers into unused slots, and {number: slot}."""
    off, lst = find_master_list(code)
    free = free_master_slots(lst)
    records, placed = [], {}
    for no in sorted(set(int(n) for n in numbers)):
        if no in lst:
            placed[no] = lst.index(no)
            continue
        if not 1 <= no <= 0xFFFE:
            raise CodeError(f"Quest number {no} can not be registered.")
        if not free:
            raise CodeError("The game's quest list is full: no room to register another quest.")
        slot = free.pop(0)
        records.append((off + 2 * slot, struct.pack("<H", no)))
        placed[no] = slot
    return records, placed


# ----------------------------------------------------------- roaming-monster lists
def _read_list(code: bytes, off: int) -> list[list[int]] | None:
    out = []
    while len(out) < 16:
        e = struct.unpack_from("<15H", code, off + ROAM_ENTRY * len(out))
        if not any(e):
            return out
        if not 0 < e[0] < 200:
            return None
        out.append(list(e))
    return None


def find_roaming(code: bytes) -> tuple[int, list[int]]:
    """(file offset of the pointer table, pointers). Slot 0 is the table's first word."""
    first = code.find(ROAM_HEAD)
    while first >= 0:
        ptr = code.find(struct.pack("<I", first + BASE))
        if ptr >= 8 and _read_list(code, first):
            base = ptr - 8                                   # the first list is slot 2
            if struct.unpack_from("<I", code, base)[0] == 0:
                ptrs = []
                while len(ptrs) < 400:
                    (v,) = struct.unpack_from("<I", code, base + 4 * len(ptrs))
                    if v and (not BASE < v < BASE + len(code) or _read_list(code, v - BASE) is None):
                        break
                    ptrs.append(v)
                while ptrs and ptrs[-1] == 0:                # zeros after the last list: not ours
                    ptrs.pop()
                return base, ptrs
        first = code.find(ROAM_HEAD, first + 1)
    raise CodeError("The roaming-monster lists were not found in code.bin (unknown game version?).")


def roaming_tables(code: bytes) -> dict[int, list[list[int]]]:
    _base, ptrs = find_roaming(code)
    return {i: _read_list(code, p - BASE) for i, p in enumerate(ptrs) if p}


def free_roaming_slots(code: bytes) -> list[int]:
    _base, ptrs = find_roaming(code)
    return [i for i, p in enumerate(ptrs) if i and not p]


def roaming_blob(entries) -> bytes:
    out = b"".join(struct.pack("<15H", *[int(v) & 0xFFFF for v in e]) for e in entries)
    return out + bytes(ROAM_ENTRY)


# ------------------------------------------------------------------ start forms
def start_forms(code: bytes, records_va: int) -> list[int]:
    """The 'form' byte of each start record of a list (index = the quest's Starttype)."""
    o, out = records_va - BASE, []
    while len(out) < 16 and struct.unpack_from("<I", code, o + 56 * len(out))[0] != 0:
        out.append(code[o + 56 * len(out) + 11])
    return out


# ------------------------------------------------------------------ quest map -> stage
STAGE_TABLE = bytes([0, 0, 1, 0x0F, 2, 0x10, 3, 0x11, 4, 0x12, 5, 0x13, 6, 0x14, 7, 0x15, 8, 0x16, 8, 8,
                     0x0B, 0x0B, 0x0A, 0x0A, 0x0B, 0x17, 0x0C, 0x18, 0x0D, 0x19, 0x0E, 0x0E])
PLACE_TABLE = bytes([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 10, 11, 12, 13, 14, 0xFF, 0xFF])
HUB_STAGES = {"village": 26, "port": 27}          # stage\\mura, stage\\minato
FREE_MAP = 9                                      # the quest map no game quest uses


def find_stage_tables(code: bytes) -> int:
    """File offset of the quest map -> stage table (the placement table follows it)."""
    off = code.find(STAGE_TABLE + PLACE_TABLE)
    if off < 0 or code.find(STAGE_TABLE + PLACE_TABLE, off + 1) >= 0:
        raise CodeError("The quest map -> stage table was not found in code.bin (unknown game version?).")
    return off


def hub_map_patch(code: bytes, hub: str, placement: int = 8) -> list[tuple[int, bytes]]:
    """Experimental: make quest map 9 load Moga Village or Port Tanzia. Large monsters there use the
    placement data of 'placement' (the Arena: the Monster pack gives it to every large monster)."""
    stage = HUB_STAGES[hub]
    off = find_stage_tables(code)
    return [(off + 2 * FREE_MAP, bytes([stage, stage])),
            (off + len(STAGE_TABLE) + FREE_MAP, bytes([placement]))]
