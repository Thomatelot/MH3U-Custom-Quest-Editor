"""Fixed equipment of the Challenge quests and Grudge Matches ("arena" block of a quest record).

After the objectives every quest ends with a 21-byte block (S and A rank times in seconds, then an
unlock rule), followed by the list of placed monsters (45-byte entries) and by the gear sets: 5 sets
of 172 bytes, each 43 pairs of u16 = weapon, two unused pairs, head, chest, waist, arms, legs,
talisman, two talisman skills (skill tree, points), 24 pouch items and 8 ammo items (item, count).
Layout from mh3u-quest-studio (Wii U), checked here on the 3DS quests: every event and challenge
quest holds 5 sets; the 10 Challenge quests of pack 4 fill them, the event quests leave them empty.

The game uses the sets only for the quests the Arena Clerk lists, by number: Grudge Matches
60000-60011 (base game) and Challenge quests 61000-61009 (read from the quest4 pack). Elsewhere the
hunters keep their own equipment, so MH3U has no "weapon type" rule for an ordinary quest.
"""
from __future__ import annotations

import json
import struct

from . import gamedata as G

END_BLOCK = 21
EM_SET_SIZE = 45
SET_SIZE = 172
SETS = 5
GEAR_QUESTS = (range(60000, 60012), range(61000, 61010))
SLOT_TYPES = {"head": 5, "chest": 1, "arms": 2, "waist": 3, "legs": 4}
SLOT_INDEX = {"weapon": 0, "head": 3, "chest": 4, "waist": 5, "arms": 6, "legs": 7, "talisman": 8}
WEAPON_TYPES = (7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19)
BOWGUNS = (11, 13)

try:
    _EQ = json.loads((G.DATA_DIR / "equipment.json").read_text(encoding="utf-8"))
except (OSError, ValueError):
    _EQ = {"types": {}, "names": {}, "skills": []}
_EQ_EN = _EQ


def set_language(code: str) -> None:
    global _EQ
    _EQ = _EQ_EN
    if code == "fr":
        try:
            _EQ = json.loads((G.DATA_DIR / "lang" / "equipment_fr.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass


def type_name(t: int) -> str:
    return _EQ["types"].get(str(t), f"type {t}")


def names(t: int) -> list[str]:
    return _EQ["names"].get(str(t), [])


def equip_name(t: int, i: int) -> str:
    if not i:
        return "(none)"
    lst = names(t)
    return lst[i] if 0 <= i < len(lst) else f"#{i}"


def skill_names() -> list[str]:
    return _EQ.get("skills", [])


def uses_gear(quest_no: int) -> bool:
    return any(quest_no in r for r in GEAR_QUESTS)


def _offsets(q):
    """(end block offset, offset of the first gear set) or None when the record has no gear sets."""
    d, pos = q.data, getattr(q, "_rest_off", None)
    if pos is None or pos + END_BLOCK + 4 > len(d):
        return None
    p = pos + END_BLOCK
    (ne,) = struct.unpack_from("<I", d, p)
    p += 4 + ne * EM_SET_SIZE
    if ne > 1000 or p + 4 > len(d):
        return None
    (na,) = struct.unpack_from("<I", d, p)
    if na != SETS or p + 4 + SETS * SET_SIZE > len(d):
        return None
    return pos, p + 4


def has_gear(q) -> bool:
    return _offsets(q) is not None


def times(q) -> tuple[int, int]:
    pos, _g = _offsets(q)
    return struct.unpack_from("<HH", q.data, pos)


def set_times(q, s_rank: int, a_rank: int) -> None:
    pos, _g = _offsets(q)
    struct.pack_into("<HH", q.data, pos, max(0, min(s_rank, 0xFFFF)), max(0, min(a_rank, 0xFFFF)))


def read_set(q, i: int) -> list[list[int]]:
    _p, g = _offsets(q)
    v = struct.unpack_from("<86H", q.data, g + i * SET_SIZE)
    return [[v[2 * k], v[2 * k + 1]] for k in range(43)]


def write_set(q, i: int, pairs: list[list[int]]) -> None:
    _p, g = _offsets(q)
    flat = [max(0, min(int(x), 0xFFFF)) for p in pairs for x in p]
    if len(flat) != 86:
        raise ValueError("a gear set holds 43 pairs")
    struct.pack_into("<86H", q.data, g + i * SET_SIZE, *flat)


def raw_sets(q) -> bytes:
    _p, g = _offsets(q)
    return bytes(q.data[g:g + SETS * SET_SIZE])


def put_raw_sets(q, blob: bytes) -> None:
    _p, g = _offsets(q)
    q.data[g:g + SETS * SET_SIZE] = blob


def pouch(pairs):
    return pairs[11:35]


def ammo(pairs):
    return pairs[35:43]


def summary(pairs) -> str:
    """'Long Sword: Bone Blade' for a set (or 'empty')."""
    t, w = pairs[0]
    if not w:
        return "empty set (own equipment)" if not any(x for p in pairs for x in p) else "no weapon"
    return f"{type_name(t)}: {equip_name(t, w)}"


def problems(q) -> list[str]:
    if not has_gear(q):
        return []
    out = []
    used = uses_gear(q.get("quest_no"))
    filled = [i for i in range(SETS) if any(x for p in read_set(q, i) for x in p)]
    if filled and not used:
        out.append("Fixed gear is set, but the game uses it only for Challenge quests 61000-61009 and "
                   "Grudge Matches 60000-60011: hunters keep their own equipment in this quest.")
    for i in filled:
        pairs = read_set(q, i)
        t, w = pairs[0]
        if not w:
            out.append(f"Gear set {i + 1} has no weapon.")
        elif t not in WEAPON_TYPES or w >= len(names(t)) > 0:
            out.append(f"Gear set {i + 1}: weapon type {t} #{w} does not exist.")
    return out
