"""'Environment: Stable / Unstable' = roaming monsters.

The quest record has six small fields about "nora" (stray) monsters, large monsters that wander
into the map besides the targets. In the game's quest list the environment is written as
"Unstable" exactly when the chance (``nora_set_per``) is above 0: this was checked on the
250 base-game quests that the wiki lists with an Environment.

    nora_set_type   1 when the quest uses the roaming-monster table, 0 otherwise
    nora_set_per    chance in percent that roaming monsters show up (0 = stable)
    nora_per_type   a second percentage: 10 / 20 / 30 / 50 / 80 / 100 in the game's quests
    nora_set_max    most roaming monsters at the same time (1 or 2)
    nora_set_table  number of the roaming-monster list. The lists are stored in the game's program
                    (see gamecode.py); data/roaming_tables.json holds what each one contains, so
                    the editor can show the species and let any list be chosen. The Monster pack
                    can add lists of your own in the unused numbers.
    nora_pekko      1 in a few quests that always have a visitor (chance 100 / 100)
"""
from __future__ import annotations

import json
from functools import lru_cache

from . import gamedata as G

FIELDS = ("nora_set_type", "nora_set_per", "nora_per_type", "nora_set_max", "nora_set_table", "nora_pekko")
STABLE = {"nora_set_type": 0, "nora_set_per": 0, "nora_per_type": 0, "nora_set_max": 1,
          "nora_set_table": 0, "nora_pekko": 0}


@lru_cache(maxsize=1)
def _sets() -> list[dict]:
    try:
        return json.loads((G.DATA_DIR / "stray_sets.json").read_text(encoding="utf-8")).get("quests", [])
    except (OSError, ValueError):
        return []


def available() -> bool:
    return bool(_sets())


def is_unstable(q) -> bool:
    return q.get("nora_set_per") > 0


def make_stable(q) -> None:
    for f, v in STABLE.items():
        q.set(f, v)


def references(map_id: int, star: int, anywhere: bool = False) -> list[dict]:
    """The game's unstable quests on this map, closest star rank first. With ``anywhere``, when no
    quest of that map is unstable (the arenas, the Great Desert...), those of every map: the
    settings (chances, how many at once) are the same kind everywhere, only the list differs, and
    any list can then be chosen."""
    out = [s for s in _sets() if s["map"] == map_id and s["per"] > 0 and s["type"] == 1]
    if not out and anywhere:
        out = [s for s in _sets() if s["per"] > 0 and s["type"] == 1]
    out.sort(key=lambda s: (s["map"] != map_id, abs(s["star"] - star), s["no"]))
    return out


def area_count(map_id: int) -> int | None:
    """Number of areas of a map (camp not counted), from data/map_zones.json."""
    try:
        d = json.loads((G.DATA_DIR / "map_zones.json").read_text(encoding="utf-8"))["maps"]
    except (OSError, ValueError, KeyError):
        return None
    z = d.get(str(map_id))
    return None if z is None else len([a for a in z if a != "0"])


def game_has_unstable(map_id: int) -> bool:
    return any(s["map"] == map_id and s["per"] > 0 for s in _sets())


def apply(q, ref: dict) -> None:
    q.set("nora_set_type", ref["type"])
    q.set("nora_set_per", ref["per"])
    q.set("nora_per_type", ref["ptype"])
    q.set("nora_set_max", ref["max"])
    q.set("nora_set_table", ref["table"])
    q.set("nora_pekko", ref["pekko"])


def reference_of(q):
    """The game quest on this map that uses the same table number, if any."""
    if not is_unstable(q):
        return None
    t = q.get("nora_set_table")
    for s in _sets():
        if s["map"] == q.get("map") and s["table"] == t and s["per"] > 0:
            return s
    return None


def describe(q) -> str:
    if not is_unstable(q):
        return "Stable: no large monsters besides the ones listed in the Monsters tab."
    mx = q.get("nora_set_max")
    return (f"Unstable: {q.get('nora_set_per')} % chance of roaming monsters, up to {mx} at the same time.")


def problems(q, pack: dict | None = None) -> list[str]:
    """Why the roaming monsters of this quest may not show up."""
    if not is_unstable(q):
        return []
    idx = q.get("nora_set_table")
    t = table(idx)
    if not t:
        return [f"Roaming-monster list {idx} is empty in the game: no monster will roam."]
    out = []
    if is_custom(idx) and idx not in {int(k) for k in (pack or {}).get("roaming", {})}:
        out.append(f"Roaming-monster list {idx} is one of yours: build and install the Monster pack again, "
                   "otherwise the game finds no list there.")
    from . import monsterpack
    bad = [G.mon_name(em) for em in dict.fromkeys(e[EM] for e in t)
           if G.stage_ok(em, q.get("map")) is False and monsterpack.pair_status(em, q.get("map"), pack)[0] != "pack"]
    if bad:
        out.append("Roaming monsters that the game can not place on " + G.map_name(q.get("map")) + ": "
                   + ", ".join(bad) + " (they will not appear; the Monster pack can add them).")
    return out


def notes(q) -> list[str]:
    """Things to know about roaming monsters on this map (not mistakes)."""
    out = []
    if is_unstable(q) and not game_has_unstable(q.get("map")):
        if area_count(q.get("map")) == 1:
            out.append("No quest of the game has roaming monsters on this one-area map: untested. A roaming "
                       "monster has no other area to come from; a Qurupeco's call picks its monster from this "
                       "same list (as in the event quest 'An Ominous Cry'), so that is the most likely way to "
                       "see one.")
        else:
            out.append("No quest of the game has roaming monsters on this map: untested.")
    return out


# ------------------------------------------------------------- the lists themselves
CUSTOM: dict[int, list[list[int]]] = {}        # lists of the user's own (Monster pack), slot -> entries
EM, HP, AT, DF, SIZE, CHANCE, ZENNY, POINTS, LEVEL = 0, 1, 2, 3, 4, 10, 12, 13, 14


@lru_cache(maxsize=1)
def _game() -> dict:
    try:
        d = json.loads((G.DATA_DIR / "roaming_tables.json").read_text(encoding="utf-8"))
        return {"tables": {int(k): v for k, v in d.get("tables", {}).items()}, "free": d.get("free_slots", [])}
    except (OSError, ValueError):
        return {"tables": {}, "free": []}


def game_tables() -> dict[int, list[list[int]]]:
    return _game()["tables"]


def free_slots() -> list[int]:
    """List numbers the game leaves empty (room for lists of your own)."""
    return list(_game()["free"])


def table(idx: int):
    """Entries of a list, the user's own first; None when the number holds no list."""
    return CUSTOM.get(idx) or game_tables().get(idx)


def is_custom(idx: int) -> bool:
    return idx in CUSTOM


def table_text(idx: int) -> str:
    """'Great Jaggi 60 % · Rathian 40 %'"""
    t = table(idx)
    if not t:
        return ""
    return "  ·  ".join(f"{G.mon_name(e[EM])} {e[CHANCE]} %" for e in t)


def table_species(idx: int) -> list[int]:
    return [e[EM] for e in table(idx) or []]


def set_table(q, idx: int) -> None:
    """Make the quest use this list; the chance settings are kept, or copied from a game quest that
    uses the list, or set to an even chance when the quest was stable."""
    if not is_unstable(q):
        ref = next((s for s in _sets() if s["table"] == idx and s["per"] > 0), None)
        if ref:
            apply(q, ref)
        else:
            for f, v in (("nora_set_type", 1), ("nora_set_per", 50), ("nora_per_type", 50),
                         ("nora_set_max", 1), ("nora_pekko", 0)):
                q.set(f, v)
    q.set("nora_set_type", 1)
    q.set("nora_set_table", idx)


def make_entry(em: int, chance: int, like: list[int]) -> list[int]:
    """A list entry for this species, as strong as the entry 'like' (health, attack, defence and
    level rows); the money and points come from the game's entry of that species closest to it."""
    e = list(like)
    e[EM], e[CHANCE] = em, chance
    same = [x for t in game_tables().values() for x in t if x[EM] == em]
    if same:
        best = min(same, key=lambda x: abs(x[HP] - like[HP]))
        e[ZENNY], e[POINTS] = best[ZENNY], best[POINTS]
    return e


def table_problems(entries) -> list[str]:
    out = []
    if not entries:
        out.append("The list is empty.")
    if sum(e[CHANCE] for e in entries) != 100:
        out.append("The chances of a list must add up to 100 %.")
    return out


def load_custom(path) -> None:
    CUSTOM.clear()
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        CUSTOM.update({int(k): [list(map(int, e)) for e in v] for k, v in d.get("lists", {}).items()})
    except (OSError, ValueError, TypeError):
        pass


def save_custom(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"lists": {str(k): v for k, v in sorted(CUSTOM.items())}}, indent=1),
                    encoding="utf-8")
