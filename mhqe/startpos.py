"""Start position of a large monster (the quest field called Starttype).

The quest file stores only a number: 0 is the game's default start, 1 to 6 are start positions
defined by the map's own data. Which area of the map each number is can not be read from the quest
file, so the editor shows, for every number, which monsters the game's own quests start there
(data/start_usage.json, built by tools/build_start_usage.py from the game's quests).
"""
from __future__ import annotations

import json

from . import gamedata as G

try:
    _D = json.loads((G.DATA_DIR / "start_usage.json").read_text(encoding="utf-8")).get("maps", {})
except (OSError, ValueError):
    _D = {}

MAX_POSITION = 6


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
