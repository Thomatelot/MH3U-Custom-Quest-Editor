"""Reference tables: monsters, items, maps, difficulty ("Nando") rows, flags.

Tables live in ``data/*.json`` (see THIRD_PARTY.md). The difficulty table was
checked against the EU 3DS ``code.bin`` (128 rows x 8 floats, identical).
"""
from __future__ import annotations

import json
import re
import struct
from collections import namedtuple
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(name: str):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


_mon = _load("monsters.json")["monsters"]
MONSTERS: dict[int, str] = {int(k): v["name"] for k, v in _mon.items()}
BASE_HP: dict[int, int] = {int(k): v["base_hp"] for k, v in _mon.items() if v["base_hp"]}
ITEMS: list[str] = _load("items_en.json")["items"]          # index == item id
_nando = _load("nando_table.json")
NANDO_ROWS: list[list[float]] = _nando["rows"]
_flags = _load("category_flags.json")
FLAG_BITS: list[dict] = _flags["bits"]
HP_CUT_MASK = int(_flags["hp_cut"]["mask"], 16)              # 0x00100010
HP_CUT = _flags["hp_cut"]["factor"]                          # 0.55
_place = _load("em_stage_placement.json")
PLACEMENT: dict[int, set[int]] = {int(k): set(v) for k, v in _place["placement"].items()}
MAP_TO_INTERNAL: dict[int, int | None] = {int(k): v for k, v in _place["quest_map_to_internal"].items()}
SUPP_SETS: dict[int, list[tuple[int, int]]] = {
    int(k): [(it["id"], it["qty"]) for it in v] for k, v in _load("supp_sets.json").items()}

MAP_NAMES = {
    1: "Deserted Island", 2: "Sandy Plains", 3: "Flooded Forest", 4: "Tundra", 5: "Volcano",
    6: "Great Desert", 7: "Underwater Ruin", 8: "Arena", 9: "Arena (variant)",
    10: "Water Arena (variant)", 11: "Sacred Land", 12: "Water Arena", 13: "Misty Peaks",
    14: "Tower", 15: "Tainted Sea",
}

TITLE_ID = "00040000000B1D00"          # Monster Hunter 3 Ultimate (EU) program id
EXTDATA_ID = "00000B1D"

_MON_KEYS = {re.sub(r"[^a-z0-9]", "", n.lower()): i for i, n in MONSTERS.items()}


def mon_name(em_id: int) -> str:
    return MONSTERS.get(em_id, f"em{em_id:03d}")


def item_name(item_id: int) -> str:
    if 0 <= item_id < len(ITEMS):
        return ITEMS[item_id]
    return f"item #{item_id}"


def map_name(m: int) -> str:
    return MAP_NAMES.get(m, f"map {m}")


def resolve_monster(value) -> int:
    """em-ID (int, '0x..') or a monster name -> em-ID."""
    if isinstance(value, int):
        return value
    try:
        return int(value, 0)
    except ValueError:
        key = re.sub(r"[^a-z0-9]", "", str(value).lower())
        if key in _MON_KEYS:
            return _MON_KEYS[key]
        raise ValueError(f"unknown monster {value!r}") from None


# ------------------------------------------------------------ difficulty rows
def _f32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def nando_row(i: int):
    return NANDO_ROWS[i] if 0 <= i < len(NANDO_ROWS) else None


Stats = namedtuple("Stats", "hp_mult atk_mult dmg_mult est_hp hp_cut")


def monster_stats(em_id: int, nando_hp: int, nando_at: int, nando_etc: int,
                  category: int = 0):
    """What the game computes at spawn: HP = base HP x row[hp][0] (x0.55 for
    challenge-style quests), attack = row[at][1], damage taken = row[etc][2].
    Returns None when an index is outside the 128-row table."""
    rh, ra, re_ = nando_row(nando_hp), nando_row(nando_at), nando_row(nando_etc)
    if rh is None or ra is None or re_ is None:
        return None
    cut = bool(category & HP_CUT_MASK)
    est = None
    base = BASE_HP.get(em_id)
    if base:
        est = int(_f32(_f32(float(base)) * _f32(rh[0])))
        if cut:
            est = int(_f32(_f32(float(est)) * _f32(HP_CUT)))
    return Stats(rh[0], ra[1], re_[2], est, cut)


def stats_text(em_id: int, nando_hp: int, nando_at: int, nando_etc: int,
               category: int = 0) -> str:
    s = monster_stats(em_id, nando_hp, nando_at, nando_etc, category)
    if s is None:
        return "Difficulty rows must be 0-127 (the game table has 128 rows)"
    hp = f"HP x{s.hp_mult:g}"
    if s.hp_cut:
        hp += " x0.55"
    if s.est_hp is not None:
        hp += f" = {s.est_hp:,} HP"
    return f"{hp}  |  attack x{s.atk_mult:g}  |  damage taken x{s.dmg_mult:g}"


def stage_ok(em_id: int, quest_map: int) -> bool | None:
    """True/False if the game has spawn data for this monster on this map,
    None when unknown (not enough data to judge)."""
    stages = PLACEMENT.get(em_id)
    internal = MAP_TO_INTERNAL.get(quest_map)
    if stages is None or internal is None:
        return None
    return internal in stages


def maps_for_monster(em_id: int) -> list[int]:
    stages = PLACEMENT.get(em_id)
    if stages is None:
        return []
    return [m for m, internal in sorted(MAP_TO_INTERNAL.items())
            if internal in stages]


# ------------------------------------------------------------- objectives
# Objective record = (type, mode, target, count). Meanings checked against the
# objective texts of the game's 403 quests.
OBJ_NAMES = {0x0000: "No objective", 0x0001: "Hunt", 0x0081: "Capture", 0x0101: "Slay",
             0x8101: "Slay small monsters", 0x0002: "Deliver", 0x0404: "Repel",
             0x2515: "Slay or repel Jhen Mohran", 0x4014: "Slay or repel Ceadeus",
             0x2000: "Repel by damage (siege)"}
OBJ_ITEM = (0x0002,)
OBJ_MONSTER = (0x0001, 0x0081, 0x0101, 0x8101, 0x0404, 0x2515, 0x4014)
# "mode" (high 16 bits of the objective word) as used by the game's quests
OBJ_MODES = {0: "The quest's only large monster", 4: "A specific monster of the quest",
             2: "Copies of it, one after another", 1: "Small monsters (count)"}
VERBS = {0x0001: "Hunt", 0x0081: "Capture", 0x0101: "Slay", 0x8101: "Slay", 0x0002: "Deliver",
         0x0404: "Repel", 0x2515: "Slay or repel", 0x4014: "Slay or repel"}


def _article(name: str) -> str:
    return ("an " if name[:1].upper() in "AEIOU" else "a ") + name


def _plural_item(name: str) -> str:
    """'Wyvern Egg' -> 'Wyvern Eggs' (items only: the game writes monster names
    without a plural, e.g. 'Slay 20 Bullfango')."""
    if name.endswith(("s", "x", "sh", "ch")):
        return name
    return name + "s"


def _count_name(n: int, name: str, item: bool = False) -> str:
    if n <= 1:
        return _article(name)
    return f"{n} {_plural_item(name) if item else name}"


def objective_sentence(q, which: int) -> str | None:
    """Plain English, close to how the game writes it."""
    typ, mode, tid, cnt = q.objective(which)
    if typ == 0:
        return None
    if typ in OBJ_ITEM:
        name = item_name(tid)
        if name == "Paw Pass Ticket":
            return "Survive until time expires or deliver a Paw Pass Ticket"
        return f"Deliver {_count_name(cnt, name, item=True)}"
    if typ == 0x2000:
        return f"Deal {cnt} siege damage"
    verb = VERBS.get(typ, OBJ_NAMES.get(typ, "Complete"))
    target = mon_name(tid)
    if typ in (0x0404, 0x2515, 0x4014):              # count is not a number of monsters
        return f"{verb} {_article(target)}"
    if mode == 4 and typ in (0x0001, 0x0081, 0x0101):
        return f"{verb} {_count_name(cnt, target)}"
    if mode == 2 and cnt > 1:
        return f"{verb} {cnt} {target} in succession"
    return f"{verb} {_count_name(cnt, target)}"


def objectives_sentence(q) -> str:
    from . import waves                                  # late import: waves needs this module
    slots = waves.used_slots(q)
    typ, mode, _tid, _cnt = q.objective(1)
    if len(slots) > 1 and typ in waves.HUNT_TYPES and mode == 4 and waves.covers_all(q):
        # the monsters arrive in groups and the last group is the target, so in effect every
        # monster has to be dealt with: write it the way the game's quest texts do
        counts: dict = {}
        for s in slots:
            counts[q.monsters[s]["Type"]] = counts.get(q.monsters[s]["Type"], 0) + max(1, q.monsters[s]["Num"])
        verb = VERBS.get(typ, "Hunt")
        names = [f"{c} {mon_name(em)}" for em, c in counts.items()]
        return f"{verb} " + (", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0])
    parts = list(dict.fromkeys(p for p in (objective_sentence(q, 1), objective_sentence(q, 2)) if p))
    if not parts:
        return "No objective set"
    if len(parts) == 1:
        return parts[0]
    joiner = {1: " and ", 2: " or "}.get(q.get("clr_pattern"), " / ")
    return parts[0] + joiner + parts[1][0].lower() + parts[1][1:]
