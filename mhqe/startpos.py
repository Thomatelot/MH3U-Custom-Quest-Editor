"""Start position of a large monster (the quest field called Starttype).

The quest file stores only a number. The game turns it into a start area with its placement
table (code.bin): for every monster and map there is a short list of start records, the number
picks one (0 = the first, the game's usual start). The start area of each record was read from
the game (data/start_areas.json); the editor also shows which monsters the game's own quests
start with each number (data/start_usage.json, built by tools/build_start_usage.py).
"""
from __future__ import annotations

import json

from . import gamedata as G

try:
    _D = json.loads((G.DATA_DIR / "start_usage.json").read_text(encoding="utf-8")).get("maps", {})
except (OSError, ValueError):
    _D = {}

try:
    _A = json.loads((G.DATA_DIR / "start_areas.json").read_text(encoding="utf-8")).get("areas", {})
except (OSError, ValueError):
    _A = {}

MAX_POSITION = 6


def areas(em: int, map_id: int, pack: dict | None = None) -> list[int] | None:
    """Start area of each position for this monster on this map (index = Starttype), from the
    game's own table, or from the monster pack for a combination the pack adds. None if unknown."""
    internal = G.MAP_TO_INTERNAL.get(map_id)
    if internal is None:
        return None
    native = _A.get(str(em), {}).get(str(internal))
    if native is not None:
        return native
    for p in (pack or {}).get("added", []):
        if p["em"] == em and p["stage"] == internal:
            return p.get("start_areas")
    return None


def positions(map_id: int) -> list[int]:
    """0 and every value the game uses on this map; values up to 6 that it never uses on this map
    are listed too (they exist on other maps), flagged by usage() == None."""
    seen = {int(k) for k in _D.get(str(map_id), {})}
    return sorted(seen | set(range(0, MAX_POSITION + 1)))


def usage(map_id: int, pos: int):
    """{'n': count, 'ex': [[em, quest no, quest name], ...]} or None if no game quest uses it here."""
    return _D.get(str(map_id), {}).get(str(pos))


def label(pos: int) -> str:
    return "Game default" if pos == 0 else f"Start position {pos}"


def describe(map_id: int, pos: int) -> str:
    u = usage(map_id, pos)
    if u is None:
        return "Not used by any game quest on this map: it may not be a valid start here."
    ex = ", ".join(G.mon_name(em) for em, _no, _n in u["ex"][:4])
    return f"Used by {u['n']} monster{'s' if u['n'] > 1 else ''} of the game's quests here, e.g. {ex}."


# --------------------------------------------------------------- map numbers
try:
    _LAB = {int(k): v for k, v in json.loads((G.DATA_DIR / "area_labels.json").read_text(encoding="utf-8"))
            .get("maps", {}).items()}
except (OSError, ValueError):
    _LAB = {}


def area_number(map_id: int, internal: int) -> int | None:
    """Number painted on the in-game map for a (game-internal) area number."""
    shown = _LAB.get(map_id)
    if shown is None:
        return internal
    return shown[internal] if 0 <= internal < len(shown) else None


def area_label(map_id: int, internal: int, monster: bool = True) -> str:
    """'area 7' with the number the in-game map shows. Area 0 is the base camp for hunters; the
    only monster start there (Ceadeus on the Underwater Ruin) is its entrance."""
    if internal == 0:
        return ("its entrance (swims into area 1)" if map_id == 7 else "its entrance off the map") \
            if monster else "base camp"
    n = area_number(map_id, internal)
    return f"area {n}" if n is not None else f"area ? (game number {internal})"


def choice_text(pos: int, areas: list[int] | None, map_id: int) -> str:
    """Text of one entry of the 'Starts in' list."""
    if areas is None:
        return f"{pos}  -  " + (label(pos) if pos else "game default")
    if 0 <= pos < len(areas):
        where = area_label(map_id, areas[pos])
        return f"{pos}  -  {'starts at' if areas[pos] == 0 else 'starts in'} {where}" + \
            ("  (usual start)" if pos == 0 else "")
    return f"{pos}  -  no such start for this monster here"


# --------------------------------------------------------------- hunters
try:
    _H = {int(k): v for k, v in json.loads((G.DATA_DIR / "hunter_starts.json").read_text(encoding="utf-8"))
          .get("maps", {}).items()}
except (OSError, ValueError):
    _H = {}

HUNTER_CHOICES = {0: "Base camp", 1: "Random area (main hunting maps)",
                  2: "Fixed area (Underwater Ruin, Sacred Land, Tainted Sea)"}


def hunter_text(map_id: int, value: int) -> str:
    """Where the hunters start on this map with this value, as the game reads its table."""
    per = _H.get(map_id)
    if not per or not 0 <= value < len(per):
        return "Base camp (the game has no start list for this value)."
    pairs = per[value]
    if len(pairs) == 1:
        a = pairs[0][0]
        return "Always at the base camp." if a == 0 else f"Always in {area_label(map_id, a, monster=False)}."
    return "At random: " + ", ".join(f"{area_label(map_id, a, monster=False)} {w}%" for a, w in pairs) + "."


def hunter_warning(map_id: int, value: int) -> str | None:
    """Why this value does nothing on this map (the hunters start at the camp), or None."""
    if value == 0:
        return None
    per = _H.get(map_id)
    if per and 0 <= value < len(per) and per[value] != [[0, 100]]:
        return None
    where = [G.map_name(m) for m, p in sorted(_H.items()) if 0 <= value < len(p) and p[value] != [[0, 100]]]
    text = f"Hunters start {value} does nothing on {G.map_name(map_id)}: the hunters start at the base camp"
    return text + (f". It changes the start only on {', '.join(where)}." if where else ".")
