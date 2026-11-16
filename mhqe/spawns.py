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


# ------------------------------------------------------------------ one place (record)
# Layout of a 45-byte record, checked on the 11,383 records of the game's quests (a tester's notes
# gave the same reading): the species (u32), how many times it comes back (u32: 1 to 8, or 255 =
# again and again), the area, how many appear there at once, the variant (a young Aptonoth...),
# then the position (x, y, z), a 0, the facing direction (0..65535 = one turn) and a 0. The other
# bytes are kept as they are.
SMALL_SPECIES = (10, 11, 13, 17, 21, 22, 23, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
                 48, 49, 50, 76, 77, 78, 79, 80, 81, 82, 83, 84, 40)
BOULDERS = (40, 79, 80, 81, 82, 83, 84)
RESPAWN_FOREVER = 255
R_EM, R_RESPAWN, R_AREA, R_COUNT, R_VARIANT, R_POS = 0, 4, 14, 15, 16, 21


class Place:
    """Read / change one record. ``bytes(place)`` gives the record back."""

    def __init__(self, rec: bytes):
        if len(rec) != REC:
            raise QuestFormatError("a small-monster place is 45 bytes")
        self.raw = bytearray(rec)

    def __bytes__(self) -> bytes:
        return bytes(self.raw)

    em = property(lambda s: struct.unpack_from("<I", s.raw, R_EM)[0],
                  lambda s, v: struct.pack_into("<I", s.raw, R_EM, int(v)))
    respawn = property(lambda s: struct.unpack_from("<I", s.raw, R_RESPAWN)[0],
                       lambda s, v: struct.pack_into("<I", s.raw, R_RESPAWN, int(v)))
    area = property(lambda s: s.raw[R_AREA], lambda s, v: s.raw.__setitem__(R_AREA, int(v) & 0xFF))
    count = property(lambda s: s.raw[R_COUNT], lambda s, v: s.raw.__setitem__(R_COUNT, int(v) & 0xFF))
    variant = property(lambda s: s.raw[R_VARIANT], lambda s, v: s.raw.__setitem__(R_VARIANT, int(v) & 0xFF))

    @property
    def pos(self) -> tuple[float, float, float, float]:
        """(x, y, z, facing)"""
        x, y, z, _w, ang, _v = struct.unpack_from("<6f", self.raw, R_POS)
        return x, y, z, ang

    @pos.setter
    def pos(self, value) -> None:
        x, y, z, ang = (float(v) for v in value)
        struct.pack_into("<3f", self.raw, R_POS, x, y, z)
        struct.pack_into("<f", self.raw, R_POS + 16, ang)


def places(q) -> list[Place]:
    return [Place(r) for r in records(q)]


def write_places(q, items) -> None:
    write(q, [bytes(p) for p in items])


@lru_cache(maxsize=None)
def variants_of(em: int) -> dict[int, int]:
    """variant -> how many of the game's places use it, for one species."""
    c: Counter = Counter()
    for e in _lists():
        for r in e["recs"]:
            if em_of(r) == em:
                c[r[R_VARIANT]] += 1
    return dict(sorted(c.items()))


@lru_cache(maxsize=None)
def game_places(map_id: int) -> dict[int, list[tuple]]:
    """area -> the different positions the game's quests use on this map, as
    (x, y, z, facing, species that use it most, number of uses), most used first."""
    seen: dict = {}
    for e in lists_for_map(map_id):
        for r in e["recs"]:
            em = em_of(r)
            if not em:
                continue
            p = Place(r)
            key = (p.area,) + tuple(round(v, 1) for v in p.pos)
            entry = seen.setdefault(key, [p.pos, Counter()])
            entry[1][em] += 1
    out: dict[int, list[tuple]] = {}
    for key, (pos, users) in seen.items():
        em, _n = users.most_common(1)[0]
        out.setdefault(key[0], []).append(pos + (em, sum(users.values())))
    for a in out:
        out[a].sort(key=lambda t: -t[5])
    return dict(sorted(out.items()))


def is_new_here(em: int, map_id: int) -> bool:
    """True if no quest of the game puts this small monster on this map (untested there)."""
    return em not in species_on_map(map_id)


def borrow_places(q, em: int, star: int, pool: str, places_n: int = 6) -> tuple[int, int]:
    """Add a species that the game never puts on this map: it takes copies of the places of the
    map's own small monsters (the most common species of the closest game list, spread over its
    areas), with variant 0. Returns (places added, species whose places were borrowed)."""
    refs = reference_lists(q.get("map"), star, pool)
    rows = [r for e in refs[:1] for r in e["recs"] if em_of(r)]
    if not rows:
        raise QuestFormatError(f"the game's quests on {G.map_name(q.get('map'))} have no small-monster place "
                               "to borrow")
    donor = Counter(em_of(r) for r in rows).most_common(1)[0][0]
    donor_rows = [r for r in rows if em_of(r) == donor]
    by_area: dict[int, list[bytes]] = {}
    for r in donor_rows:
        by_area.setdefault(r[R_AREA], []).append(r)
    picked: list[bytes] = []
    while len(picked) < places_n and any(by_area.values()):
        for a in list(by_area):
            if by_area[a] and len(picked) < places_n:
                picked.append(by_area[a].pop(0))
    take = min(len(picked), room(q))
    if take <= 0:
        raise QuestFormatError("the quest has no room left for more small monsters")
    new = []
    for r in picked[:take]:
        p = Place(r)
        p.em, p.variant = em, 0
        new.append(bytes(p))
    write(q, records(q) + new)
    return take, donor


def hub_places(q, em: int, star: int, pool: str) -> int:
    """Experimental hub map (Moga Village, Port Tanzia): the game has no position there, so the
    species gets one place in the middle of each area, on the floor (y 0), to be moved by hand.
    The other bytes come from one of the game's own places of the species."""
    hub = G.hub_areas(q.get("map")) or {}
    tpl = next((r for m in range(1, 16) for e in reference_lists(m, star, pool) for r in e["recs"]
                if em_of(r) == em), None)
    if tpl is None:
        tpl = next((r for m in range(1, 16) for e in reference_lists(m, star, pool) for r in e["recs"]
                    if em_of(r)), None)
    if tpl is None or not hub:
        raise QuestFormatError("no small-monster place to copy")
    take = min(len(hub), room(q))
    if take <= 0:
        raise QuestFormatError("the quest has no room left for more small monsters")
    new = []
    for a in sorted(hub)[:take]:
        x0, z0, x1, z1 = hub[a]
        p = Place(tpl)
        p.em, p.variant, p.area, p.count = em, 0, a, 1
        p.pos = (round((x0 + x1) / 2), 0.0, round((z0 + z1) / 2), 0)
        new.append(bytes(p))
    write(q, records(q) + new)
    return take


def problems(q) -> list[str]:
    """Small monsters on a map where the game never puts them (untested)."""
    if not readable(q) or not available():
        return []
    new = [em for em in species(q) if em and is_new_here(em, q.get("map"))]
    if not new or G.hub_areas(q.get("map")):
        return []
    return [("Small monsters that no quest of the game puts on " + G.map_name(q.get("map")) + ": "
             + ", ".join(G.mon_name(em) for em in new) + ". Untested: the game already shows some small "
             "monsters on maps where they have no data of their own, so they should appear, but they may "
             "behave oddly (when running away, for example).")]
