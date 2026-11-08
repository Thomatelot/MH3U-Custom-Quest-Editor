"""Quest sanity checks shown in the editor before saving.

Levels: "error" (the game will very likely misbehave / the file cannot be
written), "warning" (suspicious, test it in the emulator), "info".
"""
from __future__ import annotations

import math
from collections import namedtuple

from . import gamedata as G
from . import monsterpack, startpos, waves
from .quest import LANGS, NANDO_FIELDS, NANDO_MAX, OBJ_MONSTER_TYPES, Quest

Issue = namedtuple("Issue", "level text")

EVENT_RANGES = ((20000, 29999), (61000, 61999))


def validate_quest(q: Quest, taken_numbers=(), *, in_pack: bool = True,
                   fit_problem: str | None = None, monster_pack: dict | None = None,
                   pack_installed: bool = True) -> list[Issue]:
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
    if q.get("map") not in G.MAP_NAMES:
        add("warning", f"Unknown map id {q.get('map')}.")
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
        if status in ("native", "pack"):
            ar = startpos.areas(m["Type"], q.get("map"), monster_pack)
            if ar is not None and m["Starttype"] >= len(ar):
                add("error" if status == "pack" else "warning",
                    f"{name}: start position {m['Starttype']} does not exist for this monster on {where} "
                    f"(the game has {len(ar)}: 0 to {len(ar) - 1}).")
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
        if which == 2 and clr == 0:
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
