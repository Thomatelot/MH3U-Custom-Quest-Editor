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
