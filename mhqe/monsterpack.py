"""Monster placement pack: let any large monster appear on any map (a ROM hack).

The game decides where a large monster may start a quest with two kinds of data, and both are
needed (found by reverse engineering, verified in Citra with Zinogre on Sandy Plains):

1. A placement table in the executable (``exefs/code.bin``, data section). For every monster id
   it holds a list of ``{u32 stage, u32 pointer}`` ending with stage 0xFF; the pointer leads to the
   monster's start records for that stage (56 bytes each, ended by an empty record; the quest's
   Starttype picks one, byte 9 is the start area). At quest start a monster whose list has no
   entry for the quest's stage is silently not created.
2. The monster's own stage tables in ``romfs/arc/enemy/emNNN.arc``: ``em_mappos00`` (spawn and
   roaming positions per area), ``em_arearoute00`` (routes between areas), ``em_gmv00`` (gimmick
   moves), ``em_landing00`` and ``em_turnpos00`` (flying). A monster that is placed on a stage
   but has no spawn table for it crashes the game when the quest loads.

The pack gives every chosen monster a new placement list (its own entries plus, for each new
stage, the start records of a "donor" monster that lives there) and copies the donor's stage
tables into the monster's archive. Nothing in the game itself is modified: the result is a
normal mod (``romfs`` files + ``exefs/code.ips``) built from the player's own game, so it
contains no Capcom data beyond what the player already owns. Built from the same game version,
the pack is the same for everybody (see :func:`fingerprint`), which is what local multiplayer
needs: every player must use the same pack.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import shutil
import struct
import zlib
from pathlib import Path

from . import gamedata as G

PACK_FORMAT = 1
MANIFEST = "mhqe_monster_pack.json"
BASE = 0x100000                                   # code.bin file offset 0 = virtual address 0x100000
ALIGN = 0x8000                                    # data alignment of the game's ARC archives

# Internal stage ids (not quest map ids): see gamedata.MAP_TO_INTERNAL.
SIEGE_STAGES = {6, 7, 14}                          # Great Desert, Underwater Ruin, Tainted Sea
TARGET_STAGES = tuple(range(1, 15))                # every map
EXCLUDED_MONSTERS = {20, 70, 25, 85}               # Ceadeus, Goldbeard Ceadeus, Jhen Mohran, Hallowed Jhen Mohran
                                                   # (never moved; they can still lend their data)
# Maps whose residents have no route tables. Underwater Ruin: Abyssal Lagiacrus starts there in the
# game with no spawn or route table for it at all (only its start record); Great Desert: Jhen Mohran
# has a spawn table but no routes. A monster added there gets exactly what its donor has.
ROUTELESS_STAGES = {6, 7}
SPECIAL_BOSSES = {24, 75}                          # Alatreon, Dire Miralis: scripted fights, extra risk
WATER_STAGES = {9, 11}                             # the two water arenas

TABLES = {"em_arearoute00": "route", "em_turnpos00": "area", "em_landing00": "flat", "em_gmv00": "route"}
# In every game quest on a multi-area stage, a monster that has entries in one of these tables
# has one for the quest's stage; the pack keeps that rule when it chooses donors.
REQUIRED = ("em_arearoute00", "em_landing00", "em_gmv00")


class PackError(Exception):
    pass


# =================================================================== ARC archives
def arc_entries(raw: bytes, wanted=None) -> dict:
    """{name: decompressed bytes} for the entries whose leaf name is in *wanted* (all if None)."""
    if raw[:4] != b"ARC\0":
        raise PackError("not an ARC archive")
    _ver, count = struct.unpack_from("<HH", raw, 4)
    out = {}
    for i in range(count):
        nm, _th, cs, _dsf, do = struct.unpack_from("<64sIIII", raw, 12 + i * 80)
        name = nm.split(b"\0", 1)[0].decode("ascii")
        if wanted is None or name.rsplit("\\", 1)[-1] in wanted:
            out[name] = zlib.decompress(raw[do:do + cs])
    return out


def arc_replace(raw: bytes, repl: dict) -> bytes:
    """Replace whole entries (by full name); every other entry keeps its compressed bytes.
    With nothing replaced the game's archives come back byte for byte (checked on all 85)."""
    _ver, count = struct.unpack_from("<HH", raw, 4)
    ents = []
    for i in range(count):
        nm, th, cs, dsf, do = struct.unpack_from("<64sIIII", raw, 12 + i * 80)
        ents.append([nm, th, cs, dsf, raw[do:do + cs]])
    done = set()
    for e in ents:
        name = e[0].split(b"\0", 1)[0].decode("ascii")
        if name in repl:
            blob = zlib.compress(repl[name], 6)
            e[2] = len(blob)
            e[3] = (e[3] & ~0x1FFFFFFF) | len(repl[name])
            e[4] = blob
            done.add(name)
    if set(repl) - done:
        raise PackError(f"entries not found: {sorted(set(repl) - done)}")
    off = (12 + count * 80 + ALIGN - 1) // ALIGN * ALIGN
    out = bytearray(raw[:12]) + bytearray(off - 12)
    for i, e in enumerate(ents):
        struct.pack_into("<64sIIII", out, 12 + i * 80, e[0], e[1], e[2], e[3], off)
        off += len(e[4])
    out += b"".join(e[4] for e in ents)
    return bytes(out)


# =================================================================== stage tables
class Area:
    def __init__(self, no, pos, rad):
        self.no, self.pos, self.rad = no, pos, rad


class SpawnTable:
    """em_mappos00 ('EMM'): stage -> area -> positions (x, y, z, w) and radii (index, r)."""

    def __init__(self, version=0x20110223):
        self.version = version
        self.stages: dict[int, dict[int, Area]] = {}

    @classmethod
    def parse(cls, d: bytes):
        if d[:4] != b"EMM\0":
            raise PackError("not an em_mappos file")
        t = cls(struct.unpack_from("<I", d, 4)[0])
        n = struct.unpack_from("<I", d, 8)[0]
        for i in range(n):
            sid, cnt, off, _z = struct.unpack_from("<IIII", d, 0x10 + 16 * i)
            if sid == 0xFF:
                break
            areas = {}
            for j in range(cnt):
                a, c1, c2, o1, o2 = struct.unpack_from("<IHHII", d, off + 16 * j)
                if a == 0xFF:
                    break
                pos = [struct.unpack_from("<ffff", d, o1 + 16 * k) for k in range(c1)]
                rad = [struct.unpack_from("<If", d, o2 + 8 * k) for k in range(c2)]
                areas[a] = Area(a, pos, rad)
            t.stages[sid] = areas
        return t

    def build(self) -> bytes:
        n = len(self.stages) + 1
        head = bytearray(0x10 + 16 * n)
        head[0:4] = b"EMM\0"
        struct.pack_into("<II", head, 4, self.version, n)
        body = bytearray()
        for i, (sid, areas) in enumerate(self.stages.items()):
            off = len(head) + len(body)
            struct.pack_into("<IIII", head, 0x10 + 16 * i, sid, len(areas) + 1, off, 0)
            tbl = bytearray(16 * (len(areas) + 1))
            blocks = bytearray()
            cur = off + len(tbl)
            for j, a in enumerate(areas.values()):
                o1 = cur + len(blocks)
                blocks += b"".join(struct.pack("<ffff", *p) for p in a.pos)
                o2 = cur + len(blocks)
                blocks += b"".join(struct.pack("<If", *r) for r in a.rad)
                struct.pack_into("<IHHII", tbl, 16 * j, a.no, len(a.pos), len(a.rad), o1, o2)
            struct.pack_into("<IHHII", tbl, 16 * len(areas), 0xFF, 0, 0, 0, 0)
            body += tbl + blocks
        struct.pack_into("<IIII", head, 0x10 + 16 * len(self.stages), 0xFF, 0, 0, 0)
        return bytes(head + body)


class StageTable:
    """Other stage-keyed tables (EAR, EMT, EML, EMG). Each stage's region is kept as bytes with
    its internal pointers made relative, so it can be copied to another monster's file."""

    def __init__(self, header: bytes, kind: str):
        self.header, self.kind = header, kind
        self.swap = header[:3] == b"EMG"           # EMG stores (stage, offset, count)
        self.stages: dict[int, tuple[int, bytes]] = {}

    @classmethod
    def parse(cls, d: bytes, kind: str):
        t = cls(d[:8], kind)
        n = struct.unpack_from("<I", d, 8)[0]
        ents = []
        for i in range(n):
            sid, a, b, _z = struct.unpack_from("<IIII", d, 0x10 + 16 * i)
            cnt, off = (b, a) if t.swap else (a, b)
            if sid == 0xFF:
                break
            ents.append((sid, cnt, off))
        ends = [e[2] for e in ents[1:]] + [len(d)]
        for (sid, cnt, off), end in zip(ents, ends):
            reg = bytearray(d[off:end])
            t._shift(reg, cnt, -off)
            t.stages[sid] = (cnt, bytes(reg))
        return t

    def _shift(self, reg: bytearray, cnt: int, delta: int):
        if self.kind == "flat":
            return
        for j in range(cnt):
            a, c2, o, _z = struct.unpack_from("<IIII", reg, 16 * j)
            if a == 0xFF:
                break
            struct.pack_into("<I", reg, 16 * j + 8, o + delta)
            if self.kind == "route":
                ro = o + delta if delta < 0 else o
                for k in range(c2):
                    q = ro + 16 * k
                    if struct.unpack_from("<I", reg, q)[0] == 0xFF:
                        break
                    v = struct.unpack_from("<I", reg, q + 4)[0]
                    struct.pack_into("<I", reg, q + 4, v + delta)

    def build(self) -> bytes:
        n = len(self.stages) + 1
        head = bytearray(0x10 + 16 * n)
        head[0:8] = self.header
        struct.pack_into("<I", head, 8, n)
        body = bytearray()
        for i, (sid, (cnt, reg)) in enumerate(self.stages.items()):
            base = len(head) + len(body)
            r = bytearray(reg)
            self._shift(r, cnt, base)
            struct.pack_into("<IIII", head, 0x10 + 16 * i, sid, *((base, cnt) if self.swap else (cnt, base)), 0)
            body += r
        struct.pack_into("<IIII", head, 0x10 + 16 * len(self.stages), 0xFF, 0, 0, 0)
        return bytes(head + body)


class MonsterData:
    """The stage tables of one monster archive."""

    def __init__(self, raw: bytes):
        ents = arc_entries(raw, {"em_mappos00", *TABLES})
        self.names = {n.rsplit("\\", 1)[-1]: n for n in ents}
        if "em_mappos00" not in self.names:
            raise PackError("no em_mappos00 in the archive")
        self.spawn = SpawnTable.parse(ents[self.names["em_mappos00"]])
        self.tables = {k: StageTable.parse(ents[self.names[k]], kind) for k, kind in TABLES.items()
                       if k in self.names}


# =================================================================== code.bin
class GameFiles:
    """The extracted game: <root>/romfs, <root>/exefs/code.bin, <root>/exheader.bin."""

    def __init__(self, romfs):
        self.romfs = Path(romfs)
        self.root = self.romfs.parent
        self.code_path = self.root / "exefs" / "code.bin"
        self.exheader_path = self.root / "exheader.bin"
        if not (self.romfs / "arc" / "enemy" / "em001.arc").is_file():
            raise PackError(f"{self.romfs} does not look like the romfs folder of MH3U (arc/enemy is missing).")
        if not self.code_path.is_file():
            raise PackError(f"exefs/code.bin was not found next to the romfs folder ({self.code_path}).")
        self.region = detect_region(self.romfs)
        self.code = self.code_path.read_bytes()
        self.layout = self._layout()

    def _layout(self) -> dict:
        if self.exheader_path.is_file():
            x = self.exheader_path.read_bytes()
            return {"text": struct.unpack_from("<III", x, 0x10), "ro": struct.unpack_from("<III", x, 0x20),
                    "data": struct.unpack_from("<III", x, 0x30)}
        if len(self.code) == 0xBBA000:                 # EU and US 1.0 share this layout
            return {"text": (0x100000, 0xA00, 0x9FF5D0), "ro": (0xB00000, 0x84, 0x834F0),
                    "data": (0xB84000, 0x136, 0x1351A8)}
        raise PackError("exheader.bin is missing and code.bin has an unknown size.")

    def archive(self, em: int) -> Path:
        return self.romfs / "arc" / "enemy" / f"em{em:03d}.arc"


def detect_region(romfs) -> str | None:
    romfs = Path(romfs)
    for r in ("eu", "us"):
        if (romfs / "arc" / "quest" / r).is_dir() or (romfs / "quest" / r).is_dir():
            return r
    return None


def _list_at(code: bytes, va: int):
    o = va - BASE
    if not 0 <= o < len(code) - 8:
        return None
    out = []
    for _ in range(32):
        st, p = struct.unpack_from("<II", code, o)
        if st == 0xFF:
            return out
        if st > 0x1F:
            return None
        out.append((st, p))
        o += 8
    return None


def find_placement_table(code: bytes, layout: dict) -> int:
    """Virtual address of the 86-pointer placement table, found by its content (Rathian has
    stages 1, 2, 3, 8, 12 and Rathalos 1, 5, 8 in both EU and US)."""
    dva, _pages, dsize = layout["data"]
    lo, hi = dva - BASE, dva - BASE + dsize
    for o in range(lo, hi - 4 * 86, 4):
        p1, p2 = struct.unpack_from("<II", code, o + 4)
        if not (dva <= p1 < dva + dsize and dva <= p2 < dva + dsize):
            continue
        l1, l2 = _list_at(code, p1), _list_at(code, p2)
        if l1 and l2 and [s for s, _ in l1] == [1, 2, 3, 8, 12] and [s for s, _ in l2] == [1, 5, 8]:
            return o + BASE
    raise PackError("The placement table was not found in code.bin (unknown game version?).")


def read_placement(code: bytes, table_va: int) -> dict[int, list[tuple[int, int]]]:
    out = {}
    for em in range(86):
        p = struct.unpack_from("<I", code, table_va - BASE + 4 * em)[0]
        out[em] = (_list_at(code, p) or []) if p else []
    return out


def start_areas(code: bytes, records_va: int) -> list[int]:
    """Start area of each start record (index = the quest's Starttype)."""
    o, out = records_va - BASE, []
    while len(out) < 16 and struct.unpack_from("<I", code, o + 56 * len(out))[0] != 0:
        out.append(code[o + 56 * len(out) + 9])
    return out


def free_regions(code: bytes, layout: dict) -> list[list[int]]:
    """Zero padding after the read-only and code segments (mapped and readable, never used)."""
    out = []
    for seg in ("ro", "text"):
        va, pages, size = layout[seg]
        start, end = (va + size + 7) // 8 * 8, va + pages * 0x1000
        if code[start - BASE:end - BASE] != bytes(end - start):
            raise PackError(f"The padding after the {seg} segment is not empty: unknown game version?")
        out.append([start, end])
    return out


# ------------------------------------------------------------ Great Desert
# Jhen Mohran's own start list on the Great Desert holds one record (area 1), but its spawn data
# (copied to the other monsters by the pack) has areas 1 and 2. During the fight the sand ship moves
# from area 1 to area 2, so a monster left in area 1 is out of reach. The pack gives the other
# monsters a start list of their own there: record 0 = area 1 (as before), record 1 = area 2.
DESERT = 6
DESERT_SENTINEL = 0xDE5E0006
DESERT_SENTINEL_BYTES = struct.pack("<II", DESERT, DESERT_SENTINEL)


def desert_starts(code: bytes, place: dict) -> bytes | None:
    """Start records for the Great Desert: Jhen Mohran's record for area 1, the same for area 2,
    then the game's empty end record."""
    ptr = dict(place.get(25, [])).get(DESERT)
    if not ptr:
        return None
    o = ptr - BASE
    rec, end = bytearray(code[o:o + 56]), code[o + 56:o + 112]
    if rec[9] != 1 or struct.unpack_from("<I", end, 0)[0] != 0:
        return None
    rec2 = bytearray(rec)
    rec2[9] = 2
    return bytes(rec) + bytes(rec2) + bytes(end)


# ----------------------------------------------------------------- big sizes
# The quest stores a monster's size in one byte (Size, 0-255 %). At spawn the game adds a value
# from the "size spread" table picked by Sizeparam: size % = Size + value - 100 (function at
# 0x5C0754 in the EU code, no upper limit). The table holds 35 lists (u16 weight, low, high, ...,
# 0xFFFF). The pack moves the table to free space, keeps the 35 lists, leaves 35-63 empty (exact
# size; the game itself would read past its table there) and adds Sizeparam 64-82 = exact size
# +100 % to +1900 %, so Size 255 + 1900 % = up to 2155 %; the editor offers up to 2000 %.
BIG_SIZE_BASE, BIG_SIZE_STEP, BIG_SIZE_COUNT = 64, 100, 19
MAX_BIG_SIZE = 2000


def find_size_table(code: bytes, layout: dict) -> tuple[int, int] | None:
    """(VA of the size spread pointer table, file offset of the one literal pointing to it), or None."""
    first = struct.pack("<7H", 100, 98, 99, 900, 100, 105, 0xFFFF)     # list 1 of the game's table
    i = code.find(first)
    if i < 0 or code.find(first, i + 1) >= 0:
        return None
    ref = code.find(struct.pack("<I", i + BASE))
    while ref >= 0:
        if ref % 4 == 0 and struct.unpack_from("<I", code, ref - 4)[0] == 0:
            table = ref - 4 + BASE
            lit = struct.pack("<I", table)
            text_va, _pages, text_size = layout["text"]
            hits = [k for k in range(0, len(code) - 3, 4) if code[k:k + 4] == lit]
            hits = [k for k in hits if text_va <= k + BASE < text_va + text_size]
            if len(hits) == 1:
                return table, hits[0]
            return None
        ref = code.find(struct.pack("<I", i + BASE), ref + 1)
    return None


def big_size_blobs(code: bytes, table_va: int, at: int) -> bytes:
    """New pointer table (placed at VA ``at``) followed by the new lists."""
    n = BIG_SIZE_BASE + BIG_SIZE_COUNT
    old = [struct.unpack_from("<I", code, table_va - BASE + 4 * k)[0] for k in range(35)]
    lists_at = at + 4 * n
    ptrs = old + [0] * (BIG_SIZE_BASE - 35)
    lists = bytearray()
    for k in range(1, BIG_SIZE_COUNT + 1):
        ptrs.append(lists_at + len(lists))
        v = 100 + BIG_SIZE_STEP * k
        lists += struct.pack("<4H", 1000, v, v, 0xFFFF)
    return b"".join(struct.pack("<I", p) for p in ptrs) + bytes(lists)


def split_size(percent: int) -> tuple[int, int | None]:
    """Size % wanted -> (Size byte, Sizeparam or None to keep the current spread)."""
    if percent <= 255:
        return max(0, percent), None
    k = min(BIG_SIZE_COUNT, -(-(percent - 255) // BIG_SIZE_STEP))
    return percent - BIG_SIZE_STEP * k, BIG_SIZE_BASE - 1 + k


def full_size(size: int, sizeparam: int) -> int:
    """Size % of a monster, counting the pack's big-size settings."""
    if BIG_SIZE_BASE <= sizeparam < BIG_SIZE_BASE + BIG_SIZE_COUNT:
        return size + BIG_SIZE_STEP * (sizeparam - BIG_SIZE_BASE + 1)
    return size


def is_current(manifest: dict) -> bool:
    """True when the pack was built with everything this version of the editor adds."""
    return {"big_sizes", "desert_area2"} <= set(manifest.get("features", []))


def ips(records) -> bytes:
    out = bytearray(b"PATCH")
    for off, data in records:
        while data:
            chunk = data[:0xFFFF]
            out += off.to_bytes(3, "big") + len(chunk).to_bytes(2, "big") + chunk
            off += len(chunk)
            data = data[len(chunk):]
    return bytes(out + b"EOF")


# =================================================================== planning
def is_large(em: int) -> bool:
    return G.BASE_HP.get(em, 0) >= 1000


def _jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0


def _profile(m: MonsterData):
    return tuple(bool(m.tables[k].stages) if k in m.tables else False
                 for k in ("em_landing00", "em_turnpos00", "em_gmv00"))


def _score(mons, em, d, stage) -> float:
    a, b = mons[em].spawn.stages, mons[d].spawn.stages
    shared = (set(a) & set(b)) - {stage}
    habitat = sum(_jaccard(set(a[s]), set(b[s])) for s in shared) / len(shared) if shared else 0.0
    size = 1 - abs(math.log(G.BASE_HP[em] / G.BASE_HP[d])) / 3
    same = sum(x == y for x, y in zip(_profile(mons[em]), _profile(mons[d])))
    return habitat + size + same


def _donor_ok(mons, place, em, d, stage, need_tables) -> bool:
    if d == em or d not in mons or is_large(d) != is_large(em):
        return False
    if stage not in {s for s, _ in place.get(d, [])}:
        return False
    if not need_tables:
        return True
    if stage in ROUTELESS_STAGES:
        return True                                # copy what the resident has, even nothing
    if stage not in mons[d].spawn.stages:
        return False
    if len(mons[d].spawn.stages[stage]) <= 1:     # single-area stages (arenas) need no route tables
        return True
    for k in REQUIRED:
        if k in mons[em].tables and mons[em].tables[k].stages and \
                (k not in mons[d].tables or stage not in mons[d].tables[k].stages):
            return False
    return "em_arearoute00" in mons[d].tables and stage in mons[d].tables["em_arearoute00"].stages


def tables_complete(m: MonsterData, stage: int) -> bool:
    """True when the monster has every stage table the game's own quests always provide."""
    if stage in ROUTELESS_STAGES:
        return stage in m.spawn.stages
    if stage not in m.spawn.stages:
        return False
    if len(m.spawn.stages[stage]) <= 1:
        return True
    for k in REQUIRED:
        uses = k == "em_arearoute00" or (k in m.tables and m.tables[k].stages)
        if uses and (k not in m.tables or stage not in m.tables[k].stages):
            return False
    return True


def plan_pack(mons, place, monsters, stages) -> list[dict]:
    """[{em, stage, donor, tables}] for every pair the game does not allow yet."""
    out = []
    for em in monsters:
        have = {s for s, _ in place.get(em, [])}
        for st in stages:
            if st in have:
                continue                               # native: left exactly as the game has it
            need_tables = not tables_complete(mons[em], st)
            cands = [d for d in sorted(mons) if _donor_ok(mons, place, em, d, st, need_tables)]
            if not cands:
                continue
            donor = max(cands, key=lambda d: (d not in EXCLUDED_MONSTERS, _score(mons, em, d, st), -d))
            out.append({"em": em, "stage": st, "donor": donor, "tables": need_tables})
    return out


# =================================================================== building
def build(romfs, out_dir, monsters=None, stages=TARGET_STAGES, log=print) -> dict:
    """Write <out_dir>/romfs/arc/enemy/*.arc, <out_dir>/exefs/code.ips and the manifest."""
    game = GameFiles(romfs)
    code = game.code
    table_va = find_placement_table(code, game.layout)
    place = read_placement(code, table_va)
    regions = free_regions(code, game.layout)
    log(f"Reading the monster archives ({game.region or 'unknown'} version)...")
    mons = {}
    for em in range(1, 86):
        p = game.archive(em)
        if p.is_file():
            mons[em] = MonsterData(p.read_bytes())
    if monsters is None:
        monsters = [em for em in sorted(mons) if is_large(em) and em not in EXCLUDED_MONSTERS]
    plan = plan_pack(mons, place, monsters, stages)
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    enemy = out_dir / "romfs" / "arc" / "enemy"
    enemy.mkdir(parents=True)
    by_em: dict[int, list[dict]] = {}
    for p in plan:
        by_em.setdefault(p["em"], []).append(p)
    content_hash = hashlib.sha256()
    final = {}                                     # monsters whose tables change: their new data
    for em, items in sorted(by_em.items()):
        add = [p for p in items if p["tables"]]
        if not add:
            continue
        m = copy.deepcopy(mons[em])
        final[em] = m
        changed = set()
        for p in add:
            st, d = p["stage"], mons[p["donor"]]
            if st not in m.spawn.stages and st in d.spawn.stages:
                m.spawn.stages[st] = copy.deepcopy(d.spawn.stages[st])
                changed.add("em_mappos00")
            for k, tb in m.tables.items():
                if k in d.tables and st in d.tables[k].stages and st not in tb.stages \
                        and (tb.stages or k == "em_arearoute00"):          # keep the monster's own data
                    tb.stages[st] = d.tables[k].stages[st]
                    changed.add(k)
        if not changed:
            continue
        repl = {m.names[k]: (m.spawn.build() if k == "em_mappos00" else m.tables[k].build())
                for k in sorted(changed)}
        for name in sorted(repl):
            content_hash.update(name.encode() + repl[name])
        (enemy / f"em{em:03d}.arc").write_bytes(arc_replace(game.archive(em).read_bytes(), repl))
        log(f"  {G.mon_name(em)}: {len(add)} new map(s)")
    # code patch: one new placement list per monster that gains stages
    stage_arrays = {}                              # stage -> every start-record array the game has there
    for e2, lst in place.items():
        for st, ptr in lst:
            stage_arrays.setdefault(st, set()).add(ptr)
    lists = {}
    desert = desert_starts(code, place)          # Great Desert: a start in area 2 too
    for em, items in sorted(by_em.items()):
        lst = list(place[em])
        spawn = (final.get(em) or mons[em]).spawn.stages
        for p in sorted(items, key=lambda x: x["stage"]):
            st = p["stage"]
            if st == DESERT and desert is not None:
                lst.append((st, DESERT_SENTINEL))
                p["start_areas"] = [1, 2]
                continue
            ptr = dict(place[p["donor"]])[st]
            areas_ok = set(spawn.get(st, {}))
            if st not in ROUTELESS_STAGES and len(areas_ok) > 1:
                # the start list offering the most zones among those the monster has spawn data for
                best = [(len(set(start_areas(code, q))), q == ptr, -q, q) for q in stage_arrays[st]
                        if set(start_areas(code, q)) <= areas_ok]
                if best:
                    ptr = max(best)[3]
            lst.append((st, ptr))
            p["start_areas"] = start_areas(code, ptr)
        lists[em] = b"".join(struct.pack("<II", s_, q) for s_, q in lst) + struct.pack("<II", 0xFF, 0)
    # free space: the padding after two segments, plus the old lists no longer pointed to
    free = [list(r) for r in regions]
    old_users: dict[int, set] = {}
    for e2 in range(86):
        p_ = struct.unpack_from("<I", code, table_va - BASE + 4 * e2)[0]
        if p_:
            old_users.setdefault(p_, set()).add(e2)
    for p_, users in sorted(old_users.items()):
        refs = code.count(struct.pack("<I", p_))
        if users <= set(lists) and refs == len(users):    # nothing else points to it
            free.append([p_, p_ + 8 * (len(place[min(users)]) + 1)])
    merged = []
    for a_, b_ in sorted(free):                    # neighbouring old lists form one block
        if merged and a_ <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b_)
        else:
            merged.append([a_, b_])
    free = merged
    records = []
    if desert is not None and any(DESERT_SENTINEL_BYTES in b for b in lists.values()):
        slot = next((r for r in sorted(free, key=lambda r: r[1] - r[0]) if r[1] - r[0] >= len(desert)), None)
        if slot is None:
            raise PackError("Not enough free space in code.bin for the Great Desert start list.")
        pos = slot[0]
        slot[0] += (len(desert) + 7) // 8 * 8
        records.append((pos - BASE, desert))
        lists = {em: b.replace(DESERT_SENTINEL_BYTES, struct.pack("<II", DESERT, pos)) for em, b in lists.items()}
    for em in sorted(lists, key=lambda e2: -len(lists[e2])):      # biggest first
        blob = lists[em]
        slot = next((r for r in sorted(free, key=lambda r: r[1] - r[0]) if r[1] - r[0] >= len(blob)), None)
        if slot is None:
            raise PackError("Not enough free space in code.bin for the placement lists.")
        pos = slot[0]
        slot[0] += (len(blob) + 7) // 8 * 8
        records.append((pos - BASE, blob))
        records.append((table_va - BASE + 4 * em, struct.pack("<I", pos)))
    # big sizes: the size spread table, moved and extended
    big = None
    found = find_size_table(code, game.layout)
    if found:
        size_va, lit_off = found
        need = 4 * (BIG_SIZE_BASE + BIG_SIZE_COUNT) + 8 * BIG_SIZE_COUNT
        slot = next((r for r in sorted(free, key=lambda r: r[1] - r[0]) if r[1] - r[0] >= need), None)
        if slot is not None:
            pos = slot[0]
            slot[0] += (need + 7) // 8 * 8
            records.append((pos - BASE, big_size_blobs(code, size_va, pos)))
            records.append((lit_off, struct.pack("<I", pos)))
            big = {"base": BIG_SIZE_BASE, "step": BIG_SIZE_STEP, "count": BIG_SIZE_COUNT,
                   "table": f"0x{pos:X}", "game_table": f"0x{size_va:X}"}
            log(f"Big sizes: monster sizes up to {255 + BIG_SIZE_STEP * BIG_SIZE_COUNT} % enabled.")
        else:
            log("Big sizes skipped: not enough free space in code.bin.")
    else:
        log("Big sizes skipped: the size table was not found in this code.bin.")
    left = sum(b_ - a_ for a_, b_ in free)
    log(f"Free space left in code.bin: {left} bytes.")
    records.sort()
    patch = ips(records)
    (out_dir / "exefs").mkdir()
    (out_dir / "exefs" / "code.ips").write_bytes(patch)
    content_hash.update(patch)
    manifest = {
        "format": PACK_FORMAT, "region": game.region, "title_id": G.REGIONS.get(game.region, {}).get("title_id"),
        "fingerprint": content_hash.hexdigest()[:16],
        "monsters": sorted(by_em), "stages": stages,
        "added": [{k: p[k] for k in ("em", "stage", "donor", "start_areas")} for p in plan],
        "placement_table": f"0x{table_va:X}",
        "big_sizes": big,
        "features": ["big_sizes"] * bool(big) + ["desert_area2"] * bool(desert),
    }
    (out_dir / MANIFEST).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    log(f"Done: {len(plan)} monster/map pairs added for {len(by_em)} monsters, fingerprint {manifest['fingerprint']}.")
    return manifest


def native_start_areas(romfs) -> dict:
    """{em: {stage: [area per Starttype]}} read from the game's own placement table."""
    game = GameFiles(romfs)
    place = read_placement(game.code, find_placement_table(game.code, game.layout))
    return {em: {s: start_areas(game.code, p) for s, p in lst} for em, lst in place.items() if lst}


# =================================================================== installing
def read_manifest(folder) -> dict | None:
    try:
        return json.loads((Path(folder) / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def install(pack_dir, mod_dir) -> list[str]:
    """Copy the pack into a Citra/Luma title folder (<...>/mods/<title id> or luma/titles/<title id>).
    Refuses to replace a code.ips that this editor did not write. Returns the copied paths."""
    pack_dir, mod_dir = Path(pack_dir), Path(mod_dir)
    man = read_manifest(pack_dir)
    if man is None:
        raise PackError("The monster pack has not been built yet.")
    ips_dst = mod_dir / "exefs" / "code.ips"
    for other in (mod_dir / "code.ips", mod_dir / "code.bps", mod_dir / "exefs" / "code.bps",
                  mod_dir / "code.bin", mod_dir / "exefs" / "code.bin"):
        if other.exists():
            raise PackError(f"Another code mod is installed ({other}). Remove it first: two code mods "
                            "can not be combined.")
    if ips_dst.exists() and read_manifest(mod_dir) is None:
        raise PackError(f"{ips_dst} belongs to another mod. Remove it first.")
    uninstall(mod_dir)
    copied = []
    for src in sorted(pack_dir.rglob("*")):
        if src.is_file():
            dst = mod_dir / src.relative_to(pack_dir)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(str(dst))
    return copied


def uninstall(mod_dir) -> int:
    """Remove the files of an installed pack (only those listed in its manifest)."""
    mod_dir = Path(mod_dir)
    man = read_manifest(mod_dir)
    if man is None:
        return 0
    n = 0
    files = [mod_dir / "romfs" / "arc" / "enemy" / f"em{em:03d}.arc" for em in man.get("monsters", [])]
    for f in [*files, mod_dir / "exefs" / "code.ips", mod_dir / MANIFEST]:
        if f.exists():
            f.unlink()
            n += 1
    return n


# =================================================================== editor support
def pair_status(em: int, quest_map: int, manifest: dict | None):
    """('native'|'pack'|'missing'|'unknown', info) for a monster on a quest map."""
    internal = G.MAP_TO_INTERNAL.get(quest_map)
    native = G.PLACEMENT.get(em)
    if internal is None or native is None:
        return "unknown", None
    if internal in native:
        return "native", None
    if manifest:
        for p in manifest.get("added", []):
            if p["em"] == em and p["stage"] == internal:
                return "pack", p
    return "missing", None


def risk_notes(em: int, quest_map: int) -> list[str]:
    internal = G.MAP_TO_INTERNAL.get(quest_map)
    notes = []
    if em in SPECIAL_BOSSES:
        notes.append(f"{G.mon_name(em)} is a scripted boss: away from its own map it may misbehave or crash.")
    if internal in WATER_STAGES:
        notes.append("This is a water arena: a monster that can not swim may float, freeze or crash the game.")
    if internal in (10, 13):
        notes.append("This single-area arena is normally reserved for a few monsters: untested.")
    if internal in SIEGE_STAGES:
        notes.append("This is a siege map (Jhen Mohran, Ceadeus or Dire Miralis fight): the map's own "
                     "scripts may not suit another monster.")
    return notes


def fingerprint(manifest: dict | None) -> str:
    return (manifest or {}).get("fingerprint", "")
