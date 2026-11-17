"""How much monster data a quest makes the game load.

A quest loads the files of every monster it can show (romfs/arc/enemy/emNNN.arc): its large
monsters, its small monsters and its roaming monsters (counted here as the heaviest ones of its list,
as many as can roam at the same time: which ones the game loads is not known). A tester's quest
stayed on "Now Loading" for ever (the screen still moving) with far more of them than any quest of
the game: 18.7 MB on the Flooded Forest (4 large monsters, 8 small species, a roaming Brachydios),
where the game's quests load 12.2 MB at most and 14.5 MB on any map of several areas. Another one,
10.6 MB (Dire Miralis and Alatreon), loaded on the Tainted Sea, a one-area map (the arenas' quests
load up to 13.4 MB).

The real limit is not known (it is the 3DS memory left once the map is loaded), so the editor only
compares with what the game's own quests load: data/monster_load.json, made by
tools/build_monster_load.py from the unpacked size of each monster's archive (the same in the
European and American versions) and the game's quests.
"""
from __future__ import annotations

import json
from functools import lru_cache

from . import gamedata as G
from . import spawns, strays
from . import i18n
from .i18n import _

ONE_AREA_MAPS = {8, 9, 10, 11, 12, 14, 15}      # arenas, Sacred Land, Tower, Tainted Sea


@lru_cache(maxsize=1)
def _data() -> dict:
    try:
        return json.loads((G.DATA_DIR / "monster_load.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def available() -> bool:
    return bool(_data().get("sizes"))


def size(em: int) -> int:
    return int(_data().get("sizes", {}).get(str(em), 0))


def species(q) -> dict[int, str]:
    """{monster: 'large' | 'small' | 'roaming'} of every monster the quest can show."""
    out: dict[int, str] = {}
    for m in q.monsters:
        if m["Type"]:
            out.setdefault(m["Type"], "large")
    small = set()
    try:
        if spawns.readable(q):
            small |= set(spawns.species(q))
    except Exception:                    # an unreadable small-monster list: the main species only
        pass
    small |= {q.get(f) for f in ("main_zako1", "main_zako2") if q.get(f)}
    for em in sorted(small):
        out.setdefault(em, "small")
    if strays.is_unstable(q):
        # the game shows at most nora_set_max of them at a time: count the heaviest ones (worst case)
        roam = sorted({em for em in strays.table_species(q.get("nora_set_table")) if em not in out},
                      key=size, reverse=True)
        for em in roam[:max(1, q.get("nora_set_max"))]:
            out[em] = "roaming"
    return {em: kind for em, kind in out.items() if em in G.MONSTERS}


def total(q) -> int:
    return sum(size(em) for em in species(q))


def game_max(map_id: int) -> int:
    """The most that one quest of the game loads on this map (0 when no quest uses the map)."""
    return int(_data().get("maps", {}).get(str(map_id), {}).get("max", 0))


def kind_max(map_id: int) -> int:
    """The most that one quest of the game loads on any map of the same kind (one area or several)."""
    d = _data().get("kinds", {})
    return int(d.get("one_area" if map_id in ONE_AREA_MAPS else "areas", 0))


def mb(n: int) -> str:
    text = f"{n / 1048576:.1f}"
    return text.replace(".", ",") if i18n.LANG == "fr" else text


def summary(q) -> str:
    """'Monster data: 9.8 MB (the game's quests on this map: up to 9.2 MB)'"""
    if not available():
        return ""
    m = q.get("map")
    mx = game_max(m)
    text = _("Monster data: {} MB").format(mb(total(q)))
    if mx:
        text += " " + _("(the game's quests on this map: up to {} MB)").format(mb(mx))
    return text


def problems(q) -> list[tuple[str, str]]:
    """[(level, text)]: a warning above the most any quest of the game loads on a map of this kind,
    a note above the most it loads on this map."""
    if not available():
        return []
    n, m = total(q), q.get("map")
    top, here = kind_max(m), game_max(m)
    heavy = sorted(species(q), key=size, reverse=True)[:3]
    names = ", ".join(f"{G.mon_name(em)} {mb(size(em))}" for em in heavy)
    if top and n > top:
        return [("warning", _(
            "This quest loads {} MB of monster files ({}...), more than any quest of the game on a map like "
            "this one ({} MB). The game may stay on 'Now Loading' for ever (seen with a tester's quest of 18.7 "
            "MB on the Flooded Forest). Fewer large monsters, small-monster species or roaming monsters make it "
            "lighter.").format(
            mb(n), names, mb(top)))]
    if here and n > here:
        return [("info", _(
            "This quest loads {} MB of monster files, more than the game's quests on this map ({} MB) but no "
            "more than on other maps of this kind. It should load; if it stays on 'Now Loading', make it "
            "lighter.").format(mb(n), mb(here)))]
    return []
