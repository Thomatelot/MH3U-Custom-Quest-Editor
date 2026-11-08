"""Auto-fill of small monsters, supply box and rewards from the game's own quests.

Everything comes from data/autofill.json, which tools/build_benchmarks.py builds from the 365
base-game quests and the original event quests. Nothing is invented: each suggestion is the
most common choice of the game's quests that share the quest's zone and rank (or, failing that,
its rank), and the dialog says which quests it is based on. The result is only a starting point:
every value stays editable.
"""
from __future__ import annotations

import json

from . import gamedata as G

try:
    _D = json.loads((G.DATA_DIR / "autofill.json").read_text(encoding="utf-8"))
except (OSError, ValueError):
    _D = {}
SMALL: dict = _D.get("small", {})
SUPPLY: dict = _D.get("supply", {})
TEMPLATES: list = _D.get("templates", [])

POOLS = ("LR", "HR", "G")
POOL_LABEL = {"LR": "Low Rank (1-2 star)", "HR": "High Rank (3-5 star)", "G": "G Rank (6+ star)"}
SMALL_FIELDS = ("main_zako1", "main_zako2", "zako_nando_hp", "zako_nando_at", "zako_nando_etc")
SUPPLY_FIELDS = ("item_set_no", "supp_set_no", "supp_time_flag", "supp_enemy_type", "supp_enemy_num")


def available() -> bool:
    return bool(SMALL and SUPPLY and TEMPLATES)


def pool_for_star(star: int) -> str:
    return "LR" if star <= 2 else "HR" if star <= 5 else "G"


def _lookup(table: dict, map_id: int, pool: str):
    """(values, where) from the (zone, rank) entry, else the rank entry."""
    hit = table.get(f"{map_id}|{pool}")
    if hit:
        return hit, f"{G.map_name(map_id)}, {POOL_LABEL[pool]}"
    hit = table.get(f"*|{pool}")
    if hit:
        return hit, f"all zones, {POOL_LABEL[pool]} (the game has no quest of this rank on {G.map_name(map_id)})"
    return None, ""


# -------------------------------------------------------------- small monsters
def small_monsters(map_id: int, pool: str):
    vals, where = _lookup(SMALL, map_id, pool)
    if not vals:
        return None
    return {f: vals[f] for f in SMALL_FIELDS}, (
        f"Small monsters most often used on {where} ({vals['n']} of {vals['of']} quests).")


def apply_small(q, vals: dict) -> None:
    for f, v in vals.items():
        q.set(f, v)


# ------------------------------------------------------------------ supply box
def supply_box(map_id: int, pool: str):
    vals, where = _lookup(SUPPLY, map_id, pool)
    if not vals:
        return None
    return {f: vals[f] for f in SUPPLY_FIELDS}, (
        f"Supply box most often used on {where} ({vals['n']} of {vals['of']} quests).")


def apply_supply(q, vals: dict) -> None:
    for f, v in vals.items():
        q.set(f, v)


# --------------------------------------------------------------------- rewards
def reward_template(q, pool: str):
    """The game quest whose reward tables best fit this quest: same rank first, then the same
    large monsters (their materials), zone and star count."""
    mons = [m["Type"] for m in q.monsters if m["Type"]]
    best, best_score = None, -1e9
    for t in TEMPLATES:
        if not (t["r1"] or t["r2"]):
            continue
        score = 0.0
        if t["pool"] == pool:
            score += 10
        elif t["pool"] in POOLS:
            score -= 2 * abs(POOLS.index(t["pool"]) - POOLS.index(pool))
        else:
            score -= 3
        shared = len(set(mons) & set(t["mons"]))
        score += 4 * min(shared, 2)
        if mons and t["mons"] and mons[0] == t["mons"][0]:
            score += 2
        if t["map"] == q.get("map"):
            score += 2
        score -= 0.7 * abs(t["star"] - q.get("star"))
        if t["no"] < 20000:
            score += 0.5                      # prefer a guild quest to an event quest on a tie
        if score > best_score:
            best, best_score = t, score
    if best is None:
        return None
    why = []
    if best["pool"] == pool:
        why.append("same rank")
    if set(mons) & set(best["mons"]):
        why.append("same monster")
    if best["map"] == q.get("map"):
        why.append("same zone")
    return best, ("Based on the game quest '" + best["name"] + f"' ({best['star']} star, "
                  + G.map_name(best["map"]) + (", " + ", ".join(why) if why else "") + ").")


def apply_rewards(q, tpl: dict, tables=(1, 2)) -> None:
    if 1 in tables:
        q.set_reward_table(1, [tuple(r) for r in tpl["r1"]])
    if 2 in tables:
        q.set_reward_table(2, [tuple(r) for r in tpl["r2"]])


# ============================================================ rewards, all monsters
# A game quest's reward table mixes the materials of its monsters with items that have nothing
# to do with them (armor spheres, charms, ores, bones, bugs, honey...). The plan below rebuilds
# both parts: the materials of EACH large monster of your quest (as the game's quests of the
# chosen rank give them), plus the other items the game's quests of that rank and zone give.
import statistics as _st
from collections import Counter, defaultdict

_TARGET_SUM = 200            # the game's tables roll twice: chances add up to 200 %


def _rank(t: dict) -> str:
    """LR / HR / G of a game quest (event, challenge and grudge quests by their star count)."""
    return t["pool"] if t["pool"] in POOLS else pool_for_star(t["star"])


_TPL = [t for t in TEMPLATES if t["r1"]]
_HAS: dict = defaultdict(set)         # item -> indexes of the game quests whose table A holds it
_MONS: dict = defaultdict(set)        # large monster -> indexes of the game quests that have it
for _i, _t in enumerate(_TPL):
    for _item in {r[0] for r in _t["r1"]}:
        _HAS[_item].add(_i)
    for _em in set(_t["mons"]):
        _MONS[_em].add(_i)
_OWNERS: dict = {}
GENERIC_AT = 5                        # an item that 5+ monsters "own" is not a monster material


def owners_of(item: int) -> frozenset:
    """The large monsters whose materials this item is: the few monsters whose quests, together,
    hold (almost) every game quest that gives the item. Rank does not matter (a G Rank material is
    only in the G Rank quests of its monster). The monster whose quests match the item's best comes
    first, so a monster that only shares quests with another one does not steal its materials; two
    monsters can share an item (Deviljho and Savage Deviljho). An item that needs 5 or more monsters
    to be explained (a seal, a sphere, a bone...) belongs to none, and neither does an item that
    only one game quest gives."""
    if item in _OWNERS:
        return _OWNERS[item]
    have = _HAS.get(item, set())
    res = frozenset()
    if len(have) >= 2:
        ranked = sorted(((len(have & ix) / len(have | ix), em) for em, ix in _MONS.items() if have & ix),
                        key=lambda x: (-x[0], x[1]))
        covered: set = set()
        owners = []
        for _j, em in ranked:
            gain = len((have & _MONS[em]) - covered)
            if gain >= 2 or (gain >= 1 and not owners):
                owners.append(em)
                covered |= have & _MONS[em]
            if len(covered) >= 0.8 * len(have) or len(owners) >= GENERIC_AT:
                break
        if len(covered) >= 0.8 * len(have) and len(owners) < GENERIC_AT:
            res = frozenset(owners)
    _OWNERS[item] = res
    return res


def _rows_stats(refs: list, table: str = "r1") -> dict:
    """item -> (share of quests, median qty, median chance, fixed share)"""
    c = Counter()
    qty, ch, fixed = defaultdict(list), defaultdict(list), Counter()
    for t in refs:
        seen = set()
        for item, q, chance in t[table]:
            if item in seen:
                continue
            seen.add(item)
            c[item] += 1
            qty[item].append(q)
            if chance:
                ch[item].append(chance)
            else:
                fixed[item] += 1
    n = max(1, len(refs))
    return {i: (c[i] / n, int(_st.median(qty[i])), int(_st.median(ch[i])) if ch[i] else 0, fixed[i] / c[i])
            for i in c}


def _pool_refs(pool: str, wide: bool = False) -> list:
    if not wide:
        return [t for t in TEMPLATES if t["pool"] == pool and t["r1"]]
    order = sorted(POOLS, key=lambda p: abs(POOLS.index(p) - POOLS.index(pool)))
    return [t for p in order for t in TEMPLATES if t["pool"] == p and t["r1"]]


def reward_plan(q, pool: str):
    """(rows for table A, rows for table B, text) built for every large monster of the quest."""
    species = list(dict.fromkeys(m["Type"] for m in q.monsters if m["Type"]))
    refs_pool = _pool_refs(pool)
    if not refs_pool:
        return None
    target_rows = int(_st.median([len(t["r1"]) for t in refs_pool]))
    n_mon = max(1, len(species))
    per_mon = max(4, min(9, round(target_rows * 0.7 / n_mon)))

    chosen: list = []                    # (item, qty, chance, source)
    used = set()
    notes = []
    for em in species:
        refs_all = [_TPL[i] for i in sorted(_MONS.get(em, ()))]
        refs = [t for t in refs_all if _rank(t) == pool]
        rank_note = ""
        if len(refs) < 2:
            refs = refs_all
            rank_note = " (taken from other ranks: the game has few quests with it at this rank)"
        if not refs:
            notes.append(f"{G.mon_name(em)}: no game quest has it, so there is no material to suggest")
            continue
        solo = [t for t in refs if len(set(t["mons"])) == 1]
        if len(solo) >= 3:
            refs = solo
        stats = _rows_stats(refs)
        mine = [(i, st) for i, st in stats.items() if em in owners_of(i) and st[0] >= 0.4]
        mine.sort(key=lambda x: (-x[1][3], -x[1][0]))
        mine = mine[:per_mon]
        added = 0
        for item, (_share, qty, chance, fixed) in mine:
            if item in used:
                continue
            used.add(item)
            added += 1
            chosen.append((item, qty, 0 if fixed >= 0.6 else chance, em))
        shared = len(mine) - added
        notes.append(f"{G.mon_name(em)}: {added} materials from {len(refs)} game quest"
                     + ("s" if len(refs) != 1 else "") + (f" ({shared} already given by another monster)" if shared else "")
                     + rank_note)
        if not added and not shared:
            notes.append(f"  {G.mon_name(em)} has too few game quests to tell its materials from the rest")

    base = [t for t in refs_pool if t["map"] == q.get("map")]
    where = f"{G.map_name(q.get('map'))}, {POOL_LABEL[pool]}"
    if len(base) < 4:
        base, where = refs_pool, f"all zones, {POOL_LABEL[pool]}"
    gen = [(i, s) for i, s in _rows_stats(base).items() if not owners_of(i) and i not in used and s[0] >= 0.3]
    gen.sort(key=lambda x: (-x[1][3] * 0.0 - x[1][0]))
    room = max(4, target_rows - len(chosen))
    for item, (_share, qty, chance, fixed) in gen[:room]:
        chosen.append((item, qty, 0 if fixed >= 0.6 else chance, None))
    notes.append(f"other items (spheres, charms, ores, bones, bugs...): {min(room, len(gen))} from the game's "
                 f"quests on {where}")

    chosen = chosen[:32]
    rolled = [r for r in chosen if r[2] > 0]
    total = sum(r[2] for r in rolled)
    rows = []
    if rolled and total:
        scaled = [max(1, round(r[2] * _TARGET_SUM / total)) for r in rolled]
        scaled[scaled.index(max(scaled))] += _TARGET_SUM - sum(scaled)
        it = iter(scaled)
        for item, qty, chance, _em in chosen:
            rows.append((item, qty, 0 if chance == 0 else next(it)))
    else:
        rows = [(i, qn, c) for i, qn, c, _e in chosen]
    rows.sort(key=lambda r: r[2] != 0)            # guaranteed rewards first, like the game

    rows2: list = []
    refs2 = [t for t in refs_pool if t["r2"]]
    if refs2:
        best = max(refs2, key=lambda t: len(set(t["mons"]) & set(species)) * 3 + (t["map"] == q.get("map")))
        rows2 = [tuple(r) for r in best["r2"]]
    text = "Built from the game's own quests:\n" + "\n".join("• " + n for n in notes)
    return rows, rows2, text


def apply_reward_plan(q, plan) -> None:
    q.set_reward_table(1, [tuple(r) for r in plan[0]])
    q.set_reward_table(2, [tuple(r) for r in plan[1]])
