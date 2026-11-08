"""Small-monster spawn lists.

Every quest carries a list of 45-byte records, one per place where a small monster can appear
(species id, group, area and coordinates). The base-game quests keep them in ``.quest_btl`` files,
the event quests (which is what this editor writes) inside the tail of the quest record:

    tail[0:21]     header (kept as it is)
    tail[21:25]    u32 number of records
    tail[25: ...]  records, 45 bytes each; the first u32 of a record is the small-monster species
    then           a block that is kept as it is (it starts with the number 5)

``data/spawn_lists.json`` holds the lists of all the game's quests (built by
tools/build_spawns.py), which is where species and places come from when you add or fill.
"""
from __future__ import annotations

import base64
import json
import struct
import zlib
from collections import Counter
from functools import lru_cache

from . import gamedata as G
from .quest import QuestFormatError

REC = 45
HEAD = 25                                  # 21 header bytes + u32 count


@lru_cache(maxsize=1)
def _lists() -> list[dict]:
    try:
        d = json.loads((G.DATA_DIR / "spawn_lists.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for e in d.get("lists", []):
        raw = zlib.decompress(base64.b64decode(e["z"]))
        e = dict(e)
        e["recs"] = [raw[i * REC:(i + 1) * REC] for i in range(len(raw) // REC)]
        out.append(e)
    return out


def available() -> bool:
    return bool(_lists())


def em_of(rec: bytes) -> int:
    return struct.unpack_from("<I", rec, 0)[0]


def with_em(rec: bytes, em: int) -> bytes:
    return struct.pack("<I", em) + rec[4:]


# ------------------------------------------------------------------ a quest's list
def readable(q) -> bool:
    t = q.tail
    if len(t) < HEAD:
        return False
    n = struct.unpack_from("<I", t, 21)[0]
    return HEAD + n * REC <= len(t) and n < 400


def records(q) -> list[bytes]:
    t = q.tail
    if not readable(q):
        return []
    n = struct.unpack_from("<I", t, 21)[0]
    return [t[HEAD + i * REC:HEAD + (i + 1) * REC] for i in range(n)]


def write(q, recs: list[bytes]) -> None:
    """Store a new list (raises QuestFormatError if it does not fit)."""
    if not readable(q):
        raise QuestFormatError("this quest has no small-monster list that the editor can read")
    t = q.tail
    old_n = struct.unpack_from("<I", t, 21)[0]
    new = t[:21] + struct.pack("<I", len(recs)) + b"".join(recs) + t[HEAD + old_n * REC:]
    q.set_tail(new)


def is_bare(q) -> bool:
    """True for a quest whose tail holds nothing: what you get by copying a base-game quest, whose
    small monsters the game keeps in a separate file."""
    return not q.tail[21:].rstrip(b"\0")


def adopt_game_list(q, source_no: int, star: int, pool: str, donors=()) -> bool:
    """Give a quest copied from a base-game quest its small monsters: the game's own list for
    that quest, and (like every event quest has) the hidden block after the list, taken from the
    event quest of ``donors`` on the same map with the closest star rank. Returns False if there is
    nothing to copy."""
    if not available():
        return False
    entry = next((e for e in _lists() if e["no"] == source_no and e["recs"]), None)
    if entry is None:
        refs = reference_lists(q.get("map"), star, pool)
        entry = refs[0] if refs else None
    if entry is None:
        return False
    best = None
    for d in donors:
        if d is None or not readable(d) or d.get("map") != q.get("map"):
            continue
        n = struct.unpack_from("<I", d.tail, 21)[0]
        post = d.tail[HEAD + n * REC:]
        if not post.rstrip(b"\0"):
            continue
        key = abs(d.get("star") - star)
        if best is None or key < best[0]:
            best = (key, post)
    recs = list(entry["recs"])
    post = best[1].rstrip(b"\0") if best else b""
    limit = (len(q.tail) - HEAD - len(post) - 8) // REC          # places that fit in the record
    recs = shrink(recs, limit)
    tail = q.tail[:21] + struct.pack("<I", len(recs)) + b"".join(recs) + post
    q.set_tail(tail)
    return True


def shrink(recs: list[bytes], limit: int) -> list[bytes]:
    """At most *limit* places, every species keeping a share of its places."""
    if len(recs) <= limit:
        return recs
    limit = max(limit, 0)
    by: dict[int, list[int]] = {}
    for i, r in enumerate(recs):
        by.setdefault(em_of(r), []).append(i)
    keep = {em: max(1, len(ix) * limit // len(recs)) for em, ix in by.items()}
    while sum(keep.values()) > limit and any(v > 1 for v in keep.values()):
        em = max(keep, key=lambda e: keep[e])
        keep[em] -= 1
    chosen: set[int] = set()
    for em, ix in by.items():
        step = len(ix) / keep[em]
        chosen.update(ix[int(k * step)] for k in range(keep[em]))
    return [r for i, r in enumerate(recs) if i in chosen][:limit] if limit else []


def species(q) -> Counter:
    return Counter(em_of(r) for r in records(q) if em_of(r))


def room(q) -> int:
    """How many more records the quest record can take."""
    free = len(q.data) - q.used_length
    return max(0, (free - 64) // REC)


def remove(q, em: int) -> None:
    write(q, [r for r in records(q) if em_of(r) != em])


def change(q, old: int, new: int) -> None:
    write(q, [with_em(r, new) if em_of(r) == old else r for r in records(q)])


# --------------------------------------------------------------- the game's lists
def lists_for_map(map_id: int) -> list[dict]:
    return [e for e in _lists() if e["map"] == map_id]


def species_on_map(map_id: int) -> Counter:
    """small-monster species -> number of the game's quests on that map that use it"""
    c: Counter = Counter()
    for e in lists_for_map(map_id):
        for em in {em_of(r) for r in e["recs"] if em_of(r)}:
            c[em] += 1
    return c


def _closeness(e: dict, star: int, pool: str) -> float:
    return abs(e["star"] - star) + (0 if e["pool"] == pool else 2)


def reference_lists(map_id: int, star: int, pool: str) -> list[dict]:
    """The game's lists for this map, closest rank first (quests without small monsters skipped)."""
    out = [e for e in lists_for_map(map_id) if any(em_of(r) for r in e["recs"])]
    out.sort(key=lambda e: (_closeness(e, star, pool), -e["n"] % 7, e["no"]))
    return out


def fill_from(q, entry: dict) -> None:
    write(q, list(entry["recs"]))


def add_species(q, em: int, star: int, pool: str, places: int = 6) -> int:
    """Add places for a species, copying them from the game's quest on this map that has the most
    similar rank. Returns how many places were added."""
    map_id = q.get("map")
    for e in reference_lists(map_id, star, pool):
        rows = [r for r in e["recs"] if em_of(r) == em]
        if rows:
            have = records(q)
            rows = rows[:max(1, places)]
            take = min(len(rows), room(q))
            if take <= 0:
                raise QuestFormatError("the quest has no room left for more small monsters")
            write(q, have + rows[:take])
            return take
    raise QuestFormatError(f"the game's quests on {G.map_name(map_id)} have no place for {G.mon_name(em)}")
