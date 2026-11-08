"""'Environment: Stable / Unstable' = roaming monsters.

The quest record has six small fields about "nora" (stray) monsters, large monsters that wander
into the map besides the targets. In the game's quest list the environment is written as
"Unstable" exactly when the chance (``nora_set_per``) is above 0: this was checked on the
250 base-game quests that the wiki lists with an Environment.

    nora_set_type   1 when the quest uses the roaming-monster table, 0 otherwise
    nora_set_per    chance in percent that roaming monsters show up (0 = stable)
    nora_per_type   a second percentage: 10 / 20 / 30 / 50 / 80 / 100 in the game's quests
    nora_set_max    most roaming monsters at the same time (1 or 2)
    nora_set_table  number of the roaming-monster list of that map. The lists are stored in the
                    game, not in the quest: only numbers that a game quest on the same map
                    uses are known to be safe, so they can only be copied from a game quest.
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


def references(map_id: int, star: int) -> list[dict]:
    """The game's unstable quests on this map, closest star rank first."""
    out = [s for s in _sets() if s["map"] == map_id and s["per"] > 0 and s["type"] == 1]
    out.sort(key=lambda s: (abs(s["star"] - star), s["no"]))
    return out


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
