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
from .i18n import _

try:
    _D = json.loads((G.DATA_DIR / "start_usage.json").read_text(encoding="utf-8")).get("maps", {})
except (OSError, ValueError):
    _D = {}

try:
    _A = json.loads((G.DATA_DIR / "start_areas.json").read_text(encoding="utf-8")).get("areas", {})
except (OSError, ValueError):
    _A = {}

try:
    _F = json.loads((G.DATA_DIR / "start_forms.json").read_text(encoding="utf-8")).get("forms", {})
except (OSError, ValueError):
    _F = {}

MAX_POSITION = 6
# Quests of the game that use a start with a special form (shown as examples).
FORM_EXAMPLES = {(74, 1): "Clashing Fists!", (72, 3): "Descent into Hades", (72, 2): "Infernal Overlord",
                 (41, 2): "Lurkers in the Woods"}


def form(em: int, map_id: int, pos: int, pack: dict | None = None) -> int:
    """The 'form' number of a start position (0 = the ordinary monster). The game has special forms
    for Brachydios (1), Zinogre and Stygian Zinogre (2, 3) only: a start record tells the monster
    which one it is (see gamecode.py). A start of your own (Monster pack) has the form you chose."""
    mine = own_start(em, map_id, pos, pack)
    if mine is not None:
        return int(mine.get("form", 0))
    lst = _F.get(str(em), {}).get(str(G.MAP_TO_INTERNAL.get(map_id)), [])
    return lst[pos] if 0 <= pos < len(lst) else 0


def form_text(em: int, map_id: int, pos: int, pack: dict | None = None) -> str:
    f = form(em, map_id, pos, pack)
    if not f:
        return ""
    ex = FORM_EXAMPLES.get((em, f))
    return _("special form {}").format(f) + (_(" (as in '{}')").format(ex) if ex else "")


# --------------------------------------------------------------- starts of your own (Monster pack)
# Developer mode: the Monster pack can add start records of your own (another area, a special
# form). They come after the game's starts of that monster on that map: the game's numbers keep
# their meaning. Untested in the game.
CUSTOM: list[dict] = []          # {"em", "map", "area", "form", "flag" (None = as the usual start)}

try:
    _S = json.loads((G.DATA_DIR / "spawn_areas.json").read_text(encoding="utf-8")).get("areas", {})
except (OSError, ValueError):
    _S = {}


def load_custom(path) -> None:
    CUSTOM.clear()
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        for x in d.get("starts", []):
            flag = x.get("flag")
            CUSTOM.append({"em": int(x["em"]), "map": int(x["map"]), "area": int(x["area"]),
                           "form": int(x.get("form", 0)), "flag": None if flag is None else int(flag)})
    except (OSError, ValueError, TypeError, KeyError):
        pass


def save_custom(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"starts": CUSTOM}, indent=1), encoding="utf-8")


def own_start(em: int, map_id: int, pos: int, pack: dict | None) -> dict | None:
    """The start of your own with this number, as built into the Monster pack, or None."""
    internal = G.MAP_TO_INTERNAL.get(map_id)
    for x in (pack or {}).get("starts") or []:
        if x["em"] == em and x["stage"] == internal and x["index"] == pos:
            return x
    return None


def spawn_areas(em: int, map_id: int, pack: dict | None = None) -> list[int]:
    """Areas where the monster has positions on this map (its own data, or the data the pack gives
    it): the areas a start of your own can use."""
    internal = G.MAP_TO_INTERNAL.get(map_id)
    if internal is None:
        return []
    own = _S.get(str(em), {}).get(str(internal))
    if own:
        return own
    for p in (pack or {}).get("added", []):
        if p["em"] == em and p["stage"] == internal:
            return _S.get(str(p["donor"]), {}).get(str(internal), [])
    return []


def game_start_count(em: int, map_id: int, pack: dict | None = None) -> int | None:
    """How many starts the game (or the pack, for a monster it adds) has for this monster here."""
    internal = G.MAP_TO_INTERNAL.get(map_id)
    native = _A.get(str(em), {}).get(str(internal))
    if native is not None:
        return len(native)
    for p in (pack or {}).get("added", []):
        if p["em"] == em and p["stage"] == internal:
            return len(p.get("start_areas") or [])
    return None


def planned_number(i: int, pack: dict | None = None) -> int | None:
    """The Starttype number CUSTOM[i] will get once the pack is built (None if unknown)."""
    x = CUSTOM[i]
    n = game_start_count(x["em"], x["map"], pack)
    if n is None:
        return None
    return n + sum(1 for y in CUSTOM[:i] if y["em"] == x["em"] and y["map"] == x["map"])


def custom_problems(x: dict, pack: dict | None = None) -> list[str]:
    out = []
    if G.MAP_TO_INTERNAL.get(x["map"]) is None:
        out.append(_("This map has no monster starts."))
        return out
    ar = spawn_areas(x["em"], x["map"], pack)
    if game_start_count(x["em"], x["map"], pack) is None:
        out.append(_("This monster does not go on this map (not in the game; the pack adds it once built)."))
    elif ar and x["area"] not in ar:
        out.append(_("The monster has no position in this area of this map."))
    if x.get("form") and x["form"] not in {74: (1,), 41: (2, 3), 72: (2, 3)}.get(x["em"], ()):
        out.append(_("The game never gives this form to this monster: unknown effect, it may crash."))
    return out


def areas(em: int, map_id: int, pack: dict | None = None) -> list[int] | None:
    """Start area of each position for this monster on this map (index = Starttype), from the
    game's own table, or from the monster pack for a combination the pack adds. None if unknown."""
    internal = G.MAP_TO_INTERNAL.get(map_id)
    if internal is None:
        return None
    out = _A.get(str(em), {}).get(str(internal))
    if out is None:
        for p in (pack or {}).get("added", []):
            if p["em"] == em and p["stage"] == internal:
                out = p.get("start_areas")
                break
    mine = sorted((x for x in (pack or {}).get("starts") or [] if x["em"] == em and x["stage"] == internal),
                  key=lambda x: x["index"])
    if out is None or not mine:
        return out
    out = list(out[:mine[0]["index"]])          # yours come right after the game's starts
    for x in mine:
        out.append(x["area"])
    return out


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


def choice_text(pos: int, areas: list[int] | None, map_id: int, em: int | None = None,
                pack: dict | None = None) -> str:
    """Text of one entry of the 'Starts in' list."""
    if em and own_start(em, map_id, pos, pack) is not None:
        ft = form_text(em, map_id, pos, pack)
        return choice_text(pos, areas, map_id) + "  ·  " + _("your start") + ("  ·  " + ft if ft else "")
    ft = form_text(em, map_id, pos, pack) if em else ""
    if ft:
        return choice_text(pos, areas, map_id) + "  ·  " + ft
    if areas is None:
        return f"{pos}  -  " + (label(pos) if pos else "game default")
    if 0 <= pos < len(areas):
        where = area_label(map_id, areas[pos])
        return f"{pos}  -  {_('starts at' if areas[pos] == 0 else 'starts in')} {_(where)}" + \
            (_("  (usual start)") if pos == 0 else "")
    return _(f"{pos}  -  no such start for this monster here")


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


def hunter_areas(map_id: int, value: int) -> list[int]:
    """Map numbers of the areas where the hunters can start (0 = base camp)."""
    per = _H.get(map_id)
    if not per or not 0 <= value < len(per):
        return [0]
    out = []
    for a, _w in per[value]:
        n = 0 if a == 0 else area_number(map_id, a)
        if n is not None and n not in out:
            out.append(n)
    return out


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
