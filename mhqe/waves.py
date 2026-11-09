"""How the large monsters of a quest arrive, and which of them must be slain to win.

Both come from fields of the quest record that the game's own quests use consistently
(checked on all 365 base-game quests and the original event quests):

* ``start_param`` (a 16-bit field) is the ARRIVAL PATTERN of the large monsters, which are
  read in the order of their five slots:

      0   everybody is in the zone from the start                    (all single-wave quests)
      1   one after another                                          (2, 3 and 4 monsters)
      5   the first one, then the other two together                 (3 monsters)  "Mark of a Hero"
      6   the first two together, then the last one                   (3 monsters)
      4   the first one, then the middle two together, then the last (4 monsters)
      8   the first two together, then the last two together         (4 monsters)

  The groups are inferred from where the game's quests put their objective targets, and from
  which species they place side by side: every quest with a given (monster count, value) pair
  fits the same grouping. What triggers the next group has not been read from the game's code:
  it is assumed to be the death or capture of the monsters of the previous group.

* The objectives A and B of the game's multi-monster quests name the monsters of the LAST group
  (so the earlier groups have to be slain to get there), with the number of monsters of that
  species in the whole quest as the count. "All at the start" quests name up to two species.
"""
from __future__ import annotations

from . import gamedata as G

HUNT_TYPES = (0x0001, 0x0081, 0x0101)

# monster count -> [(start_param, groups, label, used by the game's own quests?)]
PATTERNS: dict[int, list[tuple[int, tuple[int, ...], str, bool]]] = {
    2: [(0, (2,), "Both at the start", True),
        (1, (1, 1), "One after the other", True)],
    3: [(0, (3,), "All three at the start", False),
        (1, (1, 1, 1), "One after another", True),
        (5, (1, 2), "The first one, then the other two together", True),
        (6, (2, 1), "The first two together, then the last one", True)],
    4: [(0, (4,), "All four at the start", False),
        (1, (1, 1, 1, 1), "One after another", True),
        (4, (1, 2, 1), "The first one, then two together, then the last one", True),
        (8, (2, 2), "Two together, then two together", True)],
    5: [(0, (5,), "All five at the start", False),
        (1, (1, 1, 1, 1, 1), "One after another", False)],
}


def used_slots(q) -> list[int]:
    return [i for i, m in enumerate(q.monsters) if m["Type"]]


def patterns_for(n: int):
    return PATTERNS.get(n, [])


def groups_of(q) -> tuple[int, ...] | None:
    """The wave grouping of the quest's monsters, or None if start_param is a value this
    editor does not know for this number of monsters."""
    n = len(used_slots(q))
    if n <= 1:
        return (n,) if n else ()
    sp = q.get("start_param")
    for val, groups, _label, _game in patterns_for(n):
        if val == sp:
            return groups
    return None


def available_value(n: int, sp: int) -> int:
    """sp if it is a known pattern for n monsters, else 0 (everybody at the start)."""
    return sp if any(v == sp for v, *_ in patterns_for(n)) else 0


def split(q, groups) -> list[list[int]]:
    """Slot numbers of each wave."""
    slots = used_slots(q)
    out, k = [], 0
    for g in groups:
        out.append(slots[k:k + g])
        k += g
    return out


def wave_names(q, groups) -> list[list[str]]:
    mons = q.monsters
    return [[G.mon_name(mons[s]["Type"]) for s in wave] for wave in split(q, groups)]


def wave_text(q, groups=None) -> str:
    """'Ivory Lagiacrus  →  Brachydios + Azure Rathalos'"""
    groups = groups if groups is not None else groups_of(q)
    if not groups:
        return ""
    return "  →  ".join(" + ".join(w) for w in wave_names(q, groups))


# ------------------------------------------------------------------ objectives
def derive(q, groups=None):
    """[(species, count)] the quest must be won with (at most two, the game has two objective
    slots) and the monster 'mode' to store, or None when the quest has no large monster."""
    slots = used_slots(q)
    if not slots:
        return None
    mons = q.monsters
    groups = groups if groups is not None else (groups_of(q) or (len(slots),))
    if len(slots) == 1:
        m = mons[slots[0]]
        return ([(m["Type"], max(1, m["Num"]))], 2 if m["Num"] > 1 else 0)
    last = split(q, groups)[-1]
    targets: list[int] = []
    for s in last:
        em = mons[s]["Type"]
        if em not in targets:
            targets.append(em)
    targets = targets[-2:]                      # two objective slots
    total = {em: sum(max(1, mons[s]["Num"]) for s in slots if mons[s]["Type"] == em) for em in targets}
    return ([(em, total[em]) for em in targets], 4)


def derived_objectives(q, groups=None):
    """[(type, mode, target, count)] for objective A and B as the game's quests write them."""
    d = derive(q, groups)
    if d is None:
        return None
    pairs, mode = d
    typ = q.objective(1)[0]
    typ = typ if typ in HUNT_TYPES else 0x0001
    out = [(typ, mode, em, cnt) for em, cnt in pairs]
    while len(out) < 2:
        out.append((0, 0, 0, 0))
    return out


def sync_objectives(q, groups=None) -> bool:
    """Write objectives A and B (and the A/B pattern) from the monsters. Returns False when the
    quest's objective is not a hunt (delivery, siege...) and was left alone."""
    typ = q.objective(1)[0]
    if typ and typ not in HUNT_TYPES:
        return False
    out = derived_objectives(q, groups)
    if out is None:
        return False
    for which, (t, mode, em, cnt) in enumerate(out, start=1):
        q.set_objective(which, t, em, cnt, mode)
    q.set("clr_pattern", 1 if out[1][0] else 0)
    return True


def in_sync(q) -> bool:
    """True if the objectives are exactly what sync_objectives would write."""
    typ = q.objective(1)[0]
    if typ and typ not in HUNT_TYPES:
        return False
    out = derived_objectives(q)
    if out is None:
        return False
    cur = [q.objective(1), q.objective(2)]
    for (t, mode, em, cnt), (ct, cm, cem, ccnt) in zip(out, cur):
        if (t, mode, em, cnt) != (ct, cm, cem, ccnt):
            return False
    return q.get("clr_pattern") == (1 if out[1][0] else 0)


def set_pattern(q, value: int) -> None:
    q.set("start_param", value)


def after_change(q, was_in_sync: bool) -> None:
    """Call after the list of large monsters changed (added, removed, replaced, reordered):
    keeps start_param valid for the new number of monsters and, if the objectives followed the
    monsters before, makes them follow again."""
    n = len(used_slots(q))
    q.set("start_param", available_value(n, q.get("start_param")) if n > 1 else 0)
    if was_in_sync:
        sync_objectives(q)


# ------------------------------------------------------------- what the player faces
def win_text(q) -> str:
    """One or two plain sentences: what wins the quest, and what is optional."""
    slots = used_slots(q)
    if not slots or q.objective(1)[0] not in HUNT_TYPES:
        return ""
    mons = q.monsters
    targets = []
    for which in (1, 2):
        typ, _mode, tid, cnt = q.objective(which)
        if typ in HUNT_TYPES and tid and cnt > 0:
            targets.append((tid, cnt))
    if not targets:
        return ""
    names = " and ".join((f"{c} " if c > 1 else "") + G.mon_name(t) for t, c in targets)
    text = f"The quest is won as soon as you have slain {names}."
    groups = groups_of(q) or (len(slots),)
    waves = split(q, groups)
    earlier = [s for w in waves[:-1] for s in w]
    tset = {t for t, _ in targets}
    optional = [G.mon_name(mons[s]["Type"]) for s in waves[-1] if mons[s]["Type"] not in tset]
    if len(waves) > 1 and earlier:
        text += " The earlier monsters come first; the next ones arrive after them."
    if optional:
        text += (" " + ", ".join(dict.fromkeys(optional)) + (" is" if len(set(optional)) == 1 else " are")
                 + " NOT required: the quest ends without " + ("it" if len(set(optional)) == 1 else "them") + ". To make everybody required, use an arrival"
                   " pattern where they come before the last group.")
    return text


def pattern_win(q, groups) -> str:
    """What the player has to slay to win if the monsters arrive in 'groups', in plain words with the
    monster numbers of the cards (#1, #2...)."""
    slots = used_slots(q)
    if len(slots) < 2:
        return ""
    d = derive(q, groups)
    if d is None:
        return ""
    tset = {em for em, _c in d[0]}
    mons = q.monsters
    num = {s: k for k, s in enumerate(slots, start=1)}
    last = split(q, groups)[-1]
    req = [s for s in slots if s not in last or mons[s]["Type"] in tset]
    opt = [s for s in last if mons[s]["Type"] not in tset]

    def names(lst):
        return ", ".join(f"#{num[s]} {G.mon_name(mons[s]['Type'])}" for s in lst)
    if not opt:
        return "To win: slay all of them."
    if len(opt) == 1:
        return f"To win: slay {names(req)}.  {names(opt)} can stay alive: the quest ends without it."
    return f"To win: slay {names(req)}.  {names(opt)} can stay alive: the quest ends without them."


def covers_all(q) -> bool:
    """True when every large monster is effectively required: the objectives name every species of
    the last group (the earlier groups have to be dealt with to get there)."""
    slots = used_slots(q)
    if len(slots) < 2:
        return True
    groups = groups_of(q) or (len(slots),)
    targets = {tid for typ, _m, tid, cnt in (q.objective(1), q.objective(2)) if typ in HUNT_TYPES and cnt > 0}
    return all(q.monsters[s]["Type"] in targets for s in split(q, groups)[-1])
