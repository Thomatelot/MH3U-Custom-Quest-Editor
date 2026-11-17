"""Quest sanity checks shown in the editor before saving.

Levels: "error" (the game will very likely misbehave / the file cannot be
written), "warning" (suspicious, test it in the emulator), "info".
"""
from __future__ import annotations

import math
from collections import namedtuple

from . import gamedata as G
from . import arena, loadsize, monsterpack, progress, rules, siege, spawns, startpos, strays, waves
from .quest import LANGS, NANDO_FIELDS, NANDO_MAX, OBJ_MONSTER_TYPES, Quest
from .i18n import _

Issue = namedtuple("Issue", "level text")

EVENT_RANGES = ((20000, 29999), (61000, 61999))


def validate_quest(q: Quest, taken_numbers=(), *, in_pack: bool = True,
                   fit_problem: str | None = None, monster_pack: dict | None = None,
                   pack_installed: bool = True, all_quests: dict | None = None) -> list[Issue]:
    out: list[Issue] = []
    add = lambda level, text: out.append(Issue(level, text))     # noqa: E731

    no = q.get("quest_no")
    if not 1 <= no <= 99999:
        add("error", f"Quest number {no} must be between 1 and 99999.")
    if no in set(taken_numbers):
        add("error", f"Quest number {no} is already used by another quest.")
    if in_pack and not any(lo <= no <= hi for lo, hi in EVENT_RANGES):
        add("warning", "Known event quests use numbers 20000-29999 and challenge "
                       "quests 61000-61999; a number outside these ranges may not "
                       "be listed where you expect.")

    for field, label in (("name", "Name"), ("objective", "Objective"),
                         ("client", "Client"), ("description", "Description")):
        for i, lang in enumerate(LANGS):
            if not q.get_text(field, i).strip():
                add("warning", f"{label} is empty in {lang.upper()}.")
                break

    if not 0 <= q.get("star") <= 9:
        add("warning", "Star rank should be between 0 and 9.")
    for text in rules.problems(q.get("special_flag"), q.get("special_cond"), q.get("special_cond2")):
        add("warning", text)
    for text in arena.problems(q):
        add("warning", text)
    for level, text in siege.problems(q):
        add(level, text)
    for level, text in strays.problem_levels(q, monster_pack):
        add(level, text)
    for level, text in loadsize.problems(q):
        add(level, text)
    for text in strays.notes(q):
        add("info", text)
    for text in spawns.problems(q):
        add("info", text)
    if q.get("prog_no") not in rules.MONSTER_RANKS:
        add("warning", f"Monster rank {q.get('prog_no')} is not one the game uses (0 to 4).")
    if rules.carves(q) == "mixed":
        add("info", "Only one of the two arena-carve flags is set: untested (General tab, Arena carves).")
    if all_quests and no in all_quests:
        for level, text in progress.problems(all_quests, no, monster_pack):
            add(level, text)
    note = rules.time_note(q)
    if note:
        add(*note)
    cat = q.get("category")
    if bool(cat & rules.DAY_BIT) == bool(cat & rules.NIGHT_BIT):
        add("warning", "The quest is set to " + ("both day and night" if cat & rules.DAY_BIT else
                                                 "neither day nor night")
            + ": every quest of the game has exactly one of the two (General tab, Time of day).")
    if q.get("map") not in G.MAP_NAMES:
        add("warning", f"Unknown map id {q.get('map')}.")
    hub = (monster_pack or {}).get("map9") or ""
    if q.get("map") == G.HUB_MAP and hub in G.HUBS:
        name = _(G.HUBS[hub]["name"])
        if pack_installed:
            add("warning", _("Experimental: map 9 loads {} (Monster pack). Untested: the game may crash when the "
                             "quest loads. Large monsters use their Arena positions, far from the ground there; "
                             "small monsters need positions you type (Developer mode, Edit places).").format(name))
        else:
            add("error", _("Map 9 loads {} only with the Monster pack installed: install it (else it is the "
                           "Arena).").format(name))
    if q.get("time_min") == 0:
        add("warning", "Time limit is 0 minutes.")
    t = q.get("time_min")
    if 99 <= t <= 120:
        add("info", f"A time limit of {t} minutes freezes the in-game clock: up to 98 minutes it counts "
                    "down, from 99 it is frozen (tested in the game with 99 and 120). The quest never "
                    "runs out of time.")
    elif t > 120:
        add("warning", f"A time limit of {t} minutes is above what was tested (99 and 120 freeze the "
                       "clock): the game may not handle it. 99 minutes already freezes the clock.")

    hw = startpos.hunter_warning(q.get("map"), q.get("supp_enemy_num"))
    if hw:
        add("info", hw)
    if (q.get("map") == siege.RUIN and q.get("supp_enemy_num") != 2
            and not any(m["Type"] in siege.CEADEUS for m in q.monsters)):
        add("info", "Underwater Ruin without Ceadeus: area 1 is closed by rocks that only Ceadeus breaks, and the "
                    "way from the base camp leads to the end of area 2 (seen in the game). The game's quests "
                    "without Ceadeus start the hunters in area 3 (General tab: Hunters start 2).")

    mons = q.monsters
    first_done = False
    seen_empty = False
    present_types = set()
    for slot, m in enumerate(mons, 1):
        if not m["Type"]:
            seen_empty = True
            continue
        present_types.add(m["Type"])
        if seen_empty:
            add("warning", f"Monster slot {slot} is used after an empty slot.")
        name = G.mon_name(m["Type"])
        if m["Type"] not in G.MONSTERS:
            add("warning", f"Monster slot {slot}: unknown monster id {m['Type']}.")
        if m["Num"] == 0:
            add("warning", f"Monster slot {slot} ({name}) has a count of 0.")
        for f in NANDO_FIELDS:
            if m[f] > NANDO_MAX:
                add("error", f"Monster slot {slot} ({name}): {f} is {m[f]}; "
                             f"difficulty rows only go up to {NANDO_MAX}.")
        where = G.map_name(q.get("map"))
        status, added = monsterpack.pair_status(m["Type"], q.get("map"), monster_pack)
        if status == "missing":
            text = (f"{name} can not start a quest on {where}: the game's placement table does not allow it, "
                    "so the game skips this monster (it never appears; tested in the game). The Monster pack "
                    "page can add this combination (ROM hack).")
            add("error" if not first_done else "warning", text)
        elif status == "pack":
            text = f"{name} on {where} is added by the Monster pack (ROM hack): an untested combination."
            if not pack_installed:
                text += (" The pack is built but not installed in Citra: install it (or copy it to your 3DS), "
                         "otherwise the monster does not appear.")
            add("info" if pack_installed else "warning", text)
            for note in monsterpack.risk_notes(m["Type"], q.get("map")):
                add("warning", f"{name}: {note}")
        sp = m["Sizeparam"]
        if sp >= 35:
            big = (monster_pack or {}).get("big_sizes")
            full = monsterpack.full_size(m["Size"], sp)
            if not big:
                add("error", f"{name}: size spread {sp} is past the end of the game's size table"
                             + (f" (size {full} % needs the Monster pack with big sizes, built with "
                                "this version of the editor, and installed)" if full != m["Size"] else "")
                             + ": the game would read garbage and may crash. Choose a size of 255 % or less, "
                               "or build and install the Monster pack.")
            elif full != m["Size"]:
                add("info" if pack_installed else "error",
                    f"{name}: size {full} % uses the Monster pack's big sizes (untested in the game: a giant "
                    "monster may clip through walls or be hard to reach)."
                    + ("" if pack_installed else " The pack is not installed: install it first."))
        if status in ("native", "pack"):
            ar = startpos.areas(m["Type"], q.get("map"), monster_pack)
            planned = [startpos.planned_number(i, monster_pack) for i, x in enumerate(startpos.CUSTOM)
                       if x["em"] == m["Type"] and x["map"] == q.get("map")]
            if ar is not None and m["Starttype"] >= len(ar):
                if m["Starttype"] in planned:
                    add("error", _("{}: start {} is one of your own starts, not in the Monster pack yet: build and "
                                   "install the pack again.").format(name, m["Starttype"]))
                else:
                    add("error" if status == "pack" else "warning",
                        f"{name}: start position {m['Starttype']} does not exist for this monster on {where} "
                        f"(the game has {len(ar)}: 0 to {len(ar) - 1}).")
            elif startpos.own_start(m["Type"], q.get("map"), m["Starttype"], monster_pack) is not None:
                add("info" if pack_installed else "error",
                    _("{}: start {} is one of your own starts (Monster pack, Developer mode): untested in the game.")
                    .format(name, m["Starttype"])
                    + ("" if pack_installed else " " + _("The pack is not installed: install it first.")))
        first_done = True

    used_n = sum(1 for m in mons if m["Type"])
    if used_n > 1:
        if any(m["Num"] > 1 for m in mons if m["Type"]):
            add("warning", "A monster card has a Count above 1 while the quest has several cards. The game's "
                           "own quests only do that with a single card (copies arriving one after another).")
        if waves.groups_of(q) is None:
            add("info", f"Arrival pattern {q.get('start_param')} is not one this editor knows for {used_n} "
                        "large monsters; it is kept as it is.")
        text = waves.win_text(q)
        if "NOT required" in text:
            add("info", text)

    clr = q.get("clr_pattern")
    for which in (1, 2):
        typ, _hi, target, count = q.objective(which)
        if typ == 0 and not target and not count:
            continue
        if typ in OBJ_MONSTER_TYPES and present_types and target not in present_types:
            add("warning", f"Objective {which} targets {G.mon_name(target)} which is "
                           f"not one of this quest's large monsters.")
        if count <= 0 and typ:
            add("warning", f"Objective {which} has a count of {count}.")
        if which == 2 and clr == 0 and typ != siege.SHIP_OBJ:
            add("info", "Objective B is filled but the pattern is 'Single objective'.")

    for table, rewards in ((1, q.reward1), (2, q.reward2)):
        for iid, num, per in rewards:
            if iid >= len(G.ITEMS):
                add("warning", f"Reward table {table}: unknown item id {iid}.")
                break
        if len(rewards) == 0 and table == 1:
            add("info", "Reward table 1 is empty.")

    reward, penalty = q.get("reward_money"), q.get("penalty")
    if penalty != math.ceil(reward / 3):
        add("info", f"Penalty is {penalty}; the game's own quests use a third of the "
                    f"reward ({math.ceil(reward / 3)}).")
    if q.get("item_set_no") not in G.SUPP_SETS:
        add("warning", f"Supply set {q.get('item_set_no')} does not exist in the game.")

    if fit_problem:
        add("error", fit_problem)
    return out


def worst(issues: list[Issue]) -> str | None:
    for level in ("error", "warning", "info"):
        if any(i.level == level for i in issues):
            return level
    return None
