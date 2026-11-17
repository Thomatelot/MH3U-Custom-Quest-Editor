"""Quest drafts written on a phone with the MH3U Quest Notebook (Android app, android/ folder).

A draft (``.mh3ud``, JSON) holds what a player writes about a quest: texts, map, star rank,
monsters, objective, money, who can join, rewards. It has none of the game's hidden data, so a
draft becomes a quest the same way "New quest" works: a game quest of the same map is copied
and the draft is applied on top of it. What the draft leaves open (supply box, small monsters,
rewards when "automatic") comes from the editor's usual tables of the game's own quests.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from . import autofill, rules, siege, spawns, startpos, strays, waves
from . import gamedata as G
from . import helptext as H
from .i18n import _
from .packs import DATA
from .quest import MON_SLOTS, NANDO_MAX, NLANG, QuestFormatError

FORMAT = "mh3u-quest-draft"
BUNDLE = "mh3u-quest-drafts"
EXT = ".mh3ud"
FILE_TYPES = [("Phone quest draft", "*.mh3ud *.json"), ("All files", "*.*")]

KINDS = {"hunt": 0x0001, "capture": 0x0081, "slay": 0x0101, "small": 0x8101, "deliver": 0x0002}
SIEGE_TYPES = (0x0404, 0x2515, 0x4014, 0x2000)
# maps that no quest of the game uses -> the map that loads the same arena (gamecode.STAGE_TABLE)
SIBLING_MAPS = {9: 8, 10: 12}
TEXTS = (("name", "name"), ("objective_text", "objective"), ("sub_objective", "sub_objective"),
         ("failure", "failure"), ("client", "client"), ("description", "description"))


class DraftError(ValueError):
    """The file is not a notebook draft, or the draft cannot be used."""


# ------------------------------------------------------------------ reading
def _int(v, lo, hi, default):
    try:
        v = int(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _rows(v):
    """Health / attack / toughness rows [hp, at, df] (0-127 each), or None."""
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        return None
    try:
        return [max(0, min(NANDO_MAX, int(x))) for x in v]
    except (TypeError, ValueError):
        return None


def clean(d: dict) -> dict:
    """A draft with every value checked and put in range (the file comes from a phone)."""
    if not isinstance(d, dict) or d.get("format") != FORMAT:
        raise DraftError("This file is not a quest written with the MH3U Quest Notebook.")
    out = {"name": str(d.get("name") or "").strip()}
    for key, _f in TEXTS[1:]:
        out[key] = str(d.get(key) or "")
    out["hub"] = "Port" if d.get("hub") == "Port" else "Village"
    out["star"] = _int(d.get("star"), 1, 9, 1)          # the game's quests go up to 9 stars
    out["rank"] = _int(d.get("rank"), 0, 4, 0)
    out["map"] = _int(d.get("map"), 1, 15, 1)
    if out["map"] not in G.MAP_NAMES:
        raise DraftError(f"Unknown map {out['map']}.")
    out["time"] = _int(d.get("time"), 1, 99, 50)
    out["fee"] = _int(d.get("fee"), 0, 9_999_999, 0)
    out["reward"] = _int(d.get("reward"), 0, 9_999_999, 0)
    out["hrp"] = _int(d.get("hrp"), 0, 9_999_999, 0)
    hr = d.get("hr")
    out["hr"] = hr if hr in rules.HR_CHOICES[1:] else None
    pl = d.get("players")
    out["players"] = pl if pl in rules.PLAYER_CHOICES else 4
    out["naked"] = bool(d.get("naked"))
    out["night"] = bool(d.get("night"))
    out["arena_carves"] = bool(d.get("arena_carves"))
    mons = []
    for m in (d.get("monsters") or [])[:MON_SLOTS]:
        if not isinstance(m, dict):
            continue
        em = _int(m.get("em"), 0, 0xFF, 0)
        if em not in G.MONSTERS:
            continue
        strength = m.get("strength")
        start = m.get("start")
        mons.append({"em": em, "count": _int(m.get("count"), 1, 99, 1), "size": _int(m.get("size"), 1, 255, 100),
                     "strength": strength if strength in H.GROUPS else None,
                     "rows": _rows(m.get("rows")),
                     "start": None if start is None else _int(start, 0, 15, 0)})
    out["monsters"] = mons
    # notebook 1.1 (draft version 2): what the PC editor's standard mode also sets
    hs = d.get("hunters")
    out["hunters"] = None if hs is None else _int(hs, 0, 2, 0)
    env = d.get("environment")
    out["environment"] = env if env in ("stable", "unstable") else None
    out["small"] = "none" if d.get("small") == "none" else "auto"
    out["small_rows"] = _rows(d.get("small_rows"))
    sup = d.get("supply")
    out["supply"] = sup if isinstance(sup, int) and not isinstance(sup, bool) and sup in G.SUPP_SETS else None
    out["arrival"] = _int(d.get("arrival"), 0, 0xFFFF, 0)
    o = d.get("objective") if isinstance(d.get("objective"), dict) else {}
    kind = o.get("kind") if o.get("kind") in KINDS else "hunt"
    out["objective"] = {"kind": kind, "item": _int(o.get("item"), 0, len(G.ITEMS) - 1, 0),
                        "em": _int(o.get("em"), 0, 0xFF, 0), "count": _int(o.get("count"), 1, 99, 1)}
    r = d.get("rewards") if isinstance(d.get("rewards"), dict) else {}
    items = []
    for x in (r.get("items") or [])[:32]:
        if isinstance(x, dict):
            iid = _int(x.get("item"), 0, len(G.ITEMS) - 1, 0)
            if iid:
                items.append((iid, _int(x.get("qty"), 1, 99, 1), _int(x.get("chance"), 0, 100, 0)))
    out["rewards"] = {"auto": bool(r.get("auto", True)) or not items, "items": items}
    out["lang"] = d.get("lang") if d.get("lang") in ("en", "fr") else "en"
    return out


def read_file(path) -> list[dict]:
    """The drafts of a .mh3ud file (one quest, or a backup of several), cleaned."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DraftError(f"This file cannot be read as a phone quest draft: {exc}") from exc
    if isinstance(data, dict) and data.get("format") == BUNDLE:
        found = [clean(d) for d in data.get("drafts") or [] if isinstance(d, dict) and d.get("format") == FORMAT]
        if not found:
            raise DraftError("This backup holds no quest.")
        return found
    return [clean(data)]


# ---------------------------------------------------------------- templates
def pool_of(d) -> str:
    return "LR" if d["rank"] in (0, 1) else "HR" if d["rank"] in (2, 3) else "G"


def group_key(d, strength=None) -> str | None:
    """The game's hub / star group the monsters' strength comes from."""
    if strength in H.GROUPS:
        return strength
    keys = [k for k in H.GROUPS if k.split()[0] == d["hub"]] or list(H.GROUPS)
    return min(keys, key=lambda k: abs(int(k.split()[1]) - d["star"]), default=None)


def is_siege(q) -> bool:
    return q.objective(1)[0] in SIEGE_TYPES or q.objective(2)[0] in SIEGE_TYPES


def template_score(d, q, cat: str, *, map_id: int | None = None, siege_ok: bool = False):
    """How well a quest fits as the copy a draft starts from (higher is better), or None when it
    must not be used: another map, a siege or Dragonship quest (unless ``siege_ok``), an arena
    special."""
    if q.get("map") != (d["map"] if map_id is None else map_id):
        return None
    if is_siege(q) and not siege_ok:
        return None
    score = 0
    if cat == "Game quests":
        cls = H.quest_class(q)
        if cls not in ("Village",) and not cls.startswith("Port"):
            return None
        score += 40
        if cls.split()[0] == d["hub"]:
            score += 20
    score -= 3 * abs(q.get("star") - d["star"])
    species = {m["em"] for m in d["monsters"]}
    score += 6 * len(species & {m["Type"] for m in q.monsters if m["Type"]})
    kind = d["objective"]["kind"]
    typ = q.objective(1)[0]
    if (kind == "deliver") == (typ == 0x0002):
        score += 5
    return score


def _best(d, candidates, **kw):
    scored = [(template_score(d, q, cat, **kw), i) for i, (_l, q, cat) in enumerate(candidates)]
    scored = [(s, i) for s, i in scored if s is not None]
    return candidates[max(scored)[1]] if scored else None


def find_template(d, candidates):
    """(label, quest, category, note) of the quest to copy among ``candidates`` (as given by the
    app's template_quests()), or None. In this order: a quest of the draft's map that is not a
    siege fight; on a map whose quests are all siege fights (the Great Desert), one of them, as
    the desktop editor does; on a map that no quest uses (the arena variants), a quest of the map
    that loads the same arena. ``note`` says which of the last two happened (None for the first)."""
    hit = _best(d, candidates)
    if hit:
        return (*hit, None)
    hit = _best(d, candidates, siege_ok=True)
    if hit:
        return (*hit, _("Every quest of the game on {} is a siege fight: the quest was made from one of them, "
                        "with your monsters and objective.").format(G.map_name(d["map"])))
    sib = SIBLING_MAPS.get(d["map"])
    if sib is not None:
        hit = _best(d, candidates, map_id=sib)
        if hit:
            return (*hit, _("No quest of the game uses {}: the quest was made from one of {}, the same arena.")
                    .format(G.map_name(d["map"]), G.map_name(sib)))
    return None


def best_template(d, candidates):
    """(label, quest, category) of the best quest to copy, or None (see find_template)."""
    hit = find_template(d, candidates)
    return hit[:3] if hit else None


# -------------------------------------------------------------------- apply
def _desert(q, d, notes) -> None:
    """The Great Desert runs the Dragonship in every quest: without its integrity (objective B)
    the ship is destroyed and the quest fails as soon as it starts (seen in the game, 1.4.1)."""
    if siege.jhen_of(q) is not None:
        siege.apply_ship(q, failure_text=not d["failure"].strip())
        notes.append(_("Great Desert: set up like the game's Dragonship fights (objective and Dragonship "
                       "integrity)."))
    elif q.objective(2)[0] == 0:
        q.set_objective(2, siege.SHIP_OBJ, siege.SHIP_ID, siege.JHEN[25], 0)
        q.set("clr_pattern", 0)
        q.set("category", q.get("category") | siege.SHIP_BIT)
        notes.append(_("Great Desert without a Jhen Mohran: the Dragonship integrity was kept as objective B "
                       "(not a goal) so the ship is not destroyed at the start. Untested in the game."))
    else:
        notes.append(_("Great Desert: objective B is taken by your second monster, so the Dragonship has no "
                       "integrity and the quest may fail as soon as it starts. Untested in the game."))


def _spread_starts(q, pack) -> None:
    """Same rule as the Monsters tab: copies of one species start on different spots."""
    seen: dict = {}
    for i, m in enumerate(q.monsters):
        if not m["Type"]:
            continue
        ar = startpos.areas(m["Type"], q.get("map"), pack)
        n = len(ar) if ar else 1
        if m["Starttype"] >= n:
            q.set_monster(i, Starttype=0)
        k = seen.get(m["Type"], 0)
        if k > 0 and q.monsters[i]["Starttype"] == 0 and n > 1:
            q.set_monster(i, Starttype=k % n)
        seen[m["Type"]] = k + 1


def apply(q, d, *, pack=None, source_no=None, donors=()) -> list[str]:
    """Write draft ``d`` (cleaned) into ``q``, a copy of a quest of the same map. Returns notes
    for the user: what was filled in for them and what could not be applied."""
    notes: list[str] = []
    if q.get("map") != d["map"]:
        if SIBLING_MAPS.get(d["map"]) != q.get("map"):
            raise DraftError("The quest to copy must be on the draft's map.")
        q.set("map", d["map"])                    # same arena (see SIBLING_MAPS)
    bare = spawns.is_bare(q)
    if bare:
        q.pad_to(DATA)        # a base-game quest is shorter than an event slot: room for its small monsters

    # texts: the phone writes one language; the game shows the console's, so all five get it
    for key, field in TEXTS:
        text = d[key].replace("\r\n", "\n").replace("\n", "\r\n")
        if text.strip():
            q.set_text(field, text, langs=range(NLANG))
        elif key == "name":
            q.set_text(field, "My Custom Quest", langs=range(NLANG))
    if not d["failure"].strip():
        notes.append(_("Failure conditions: the text of the quest it was copied from was kept."))

    # quest settings
    q.set("star", d["star"])
    q.set("prog_no", d["rank"])
    q.set("time_min", d["time"])
    q.set("contract", d["fee"])
    q.set("reward_money", d["reward"])
    q.set("penalty", math.ceil(d["reward"] / 3))
    q.set("main_hrp", d["hrp"])
    rules.set_night(q, d["night"])
    rules.set_carves(q, d["arena_carves"])
    req = rules.Req(d["hr"], d["players"], d["naked"])
    conds = rules.conds_for(req)
    if conds is None:
        req = rules.Req(d["hr"], d["players"], False)
        conds = rules.conds_for(req)
        notes.append(_("Who can join: the game holds two rules at most, so 'No armor or talismans' was left out."))
    if conds is not None:
        q.set("special_cond", conds[0])
        q.set("special_cond2", conds[1])
        q.set("special_flag", rules.flag_for(req, q.get("special_flag"), rules.is_arena(q)))

    # large monsters
    for i in range(MON_SLOTS):
        q.clear_monster(i)
    cards = d["monsters"]
    if len(cards) > 1 and any(m["count"] > 1 for m in cards):
        # several cards: one monster per card, as in the game's quests (copies are extra cards)
        cards = [dict(m, count=1) for m in cards for _k in range(m["count"])]
        if len(cards) > MON_SLOTS:
            notes.append(_("Monsters: a quest holds {} large monsters at most, the last ones were left out.")
                         .format(MON_SLOTS))
            cards = cards[:MON_SLOTS]
    for i, m in enumerate(cards):
        q.set_monster(i, Type=m["em"])
        block = H.default_monster_values(q)
        key = group_key(d, m["strength"])
        if key:
            hp, at, df = H.preset_rows(key)
            block.update(Nando_hp=hp, Nando_at=at, Nando_etc=df, **H.preset_extra(key))
        if m["rows"]:
            block.update(Nando_hp=m["rows"][0], Nando_at=m["rows"][1], Nando_etc=m["rows"][2])
        block.update(Num=m["count"], Size=m["size"], Starttype=0)   # a single card may hold copies
        if m["size"] != 100:
            block["Sizeparam"] = 0                # fixed size, as the size presets do
        q.set_monster(i, **block)
    _spread_starts(q, pack)
    for i, m in enumerate(cards):                 # starts chosen on the phone (the game's own list)
        if m["start"] is None:
            continue
        ar = startpos.areas(m["em"], q.get("map"), pack)
        if ar and m["start"] < len(ar):
            q.set_monster(i, Starttype=m["start"])
        else:
            notes.append(_("{}: the start chosen on the phone does not exist on this map; the usual start is "
                           "used.").format(G.mon_name(m["em"])))
    n = len(cards)
    q.set("start_param", waves.available_value(n, d["arrival"]) if n > 1 else 0)

    # where the hunters start, roaming monsters
    if d["hunters"] is not None:
        q.set("supp_enemy_num", d["hunters"])
    if d["environment"] == "stable":
        strays.make_stable(q)
    elif d["environment"] == "unstable":
        refs = strays.references(d["map"], d["star"], anywhere=True)
        if refs:
            strays.apply(q, refs[0])
            if refs[0]["map"] != d["map"]:
                notes.append(_("Roaming monsters: no quest of the game has them on this map; the settings of "
                               "\"{}\" were used (untested here). Choose the list on the General tab.")
                             .format(refs[0].get("name", refs[0]["no"])))

    # objective
    o = d["objective"]
    kind = o["kind"]
    if kind in ("hunt", "capture", "slay"):
        q.set_objective(1, KINDS[kind], 0, 0, 0)
        q.set_objective(2, 0, 0, 0, 0)
        if not waves.sync_objectives(q):
            notes.append(_("Objective: the quest has no large monster, set the objective on the General tab."))
    elif kind == "deliver":
        q.set_objective(1, KINDS[kind], o["item"], o["count"], 0)
        q.set_objective(2, 0, 0, 0, 0)
        q.set("clr_pattern", 0)
    else:
        q.set_objective(1, KINDS[kind], o["em"], o["count"], 1)
        q.set_objective(2, 0, 0, 0, 0)
        q.set("clr_pattern", 0)
    if q.get("map") == siege.DESERT:
        _desert(q, d, notes)
    if not d["objective_text"].strip():
        q.set_text("objective", G.objectives_sentence(q), langs=range(NLANG))
        notes.append(_("Objective text: written from the objective."))

    # what the draft does not hold: small monsters and supply box of the game's quests
    pool = pool_of(d)
    if bare and source_no is not None:
        try:
            spawns.adopt_game_list(q, source_no, d["star"], pool, donors)
        except QuestFormatError:
            pass
    if d["small"] == "none" and spawns.readable(q):
        spawns.write(q, [])
        notes.append(_("Small monsters: none, as chosen on the phone."))
    if d["small_rows"]:
        for field, v in zip(("zako_nando_hp", "zako_nando_at", "zako_nando_etc"), d["small_rows"]):
            q.set(field, v)
    if d["supply"] is not None:
        q.set("item_set_no", d["supply"])
    elif autofill.available():
        res = autofill.supply_box(d["map"], pool)
        if res:
            autofill.apply_supply(q, res[0])
            notes.append(_(res[1]))
        if d["rewards"]["auto"]:
            plan = autofill.reward_plan(q, pool)
            if plan:
                autofill.apply_reward_plan(q, plan)
                notes.append(_("Rewards: chosen automatically from the game's quests of the same rank "
                               "(see the Rewards tab)."))
    if not d["rewards"]["auto"]:
        q.set_reward_table(1, d["rewards"]["items"])
        q.set_reward_table(2, [])
    elif not autofill.available():
        notes.append(_("Rewards: those of the quest it was copied from were kept."))
    return notes
