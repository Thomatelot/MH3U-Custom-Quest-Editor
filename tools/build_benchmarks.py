"""Developer tool: compute data/benchmarks.json from YOUR game files.

The tooltips of the editor quote these numbers ("like Port 7 star (G2)",
"values used by the game's quests", ...). Run:

  python tools/build_benchmarks.py --quests <romfs>/quest/eu --packs <extdata user folder> --out data

Quest numbers tell the hub (checked against the MH3U wiki quest lists):
  1000-2999 Village 1-9 star, 11000-12999 Port 1-8 star (1-2 Low Rank, 3-5 High
  Rank, 6-8 G Rank = G1-G3), 20000-29999 event quests, 60000+ Grudge Matches,
  61000+ challenge quests.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from mhqe import gamedata as G  # noqa: E402
from mhqe.packs import PACK_NAMES, EventPack  # noqa: E402
from mhqe.quest import MON_FIELDS, Quest  # noqa: E402


def quest_class(q) -> str:
    n, s = q.get("quest_no"), q.get("star")
    if n < 1000:
        return "Tutorial"
    if n < 3000:
        return "Village"
    if n < 13000:
        return "Port LR" if s <= 2 else "Port HR" if s <= 5 else "Port G"
    if n < 30000:
        return "Event"
    if n < 61000:
        return "Grudge"
    return "Challenge"


def group_key(q):
    c = quest_class(q)
    if c == "Village":
        return f"Village {q.get('star')}"
    if c.startswith("Port"):
        return f"Port {q.get('star')}"
    return None


def pool_of(q) -> str:
    """Strength pool used for the rank estimate and for the auto-fill."""
    c = quest_class(q)
    s = q.get("star")
    if c == "Village":
        return "LR" if s <= 5 else "HR"           # Village 1-5 ~ Low Rank, 6-9 ~ High Rank
    return {"Port LR": "LR", "Port HR": "HR", "Port G": "G"}.get(c, c)


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))]


def build_tiers(every):
    """Row thresholds per stat: a value strictly below LR/HR/G is that tier, a value up to
    MAX is the hardest G Rank, above MAX is Nightmare (harder than anything in the game)."""
    rows = collections.defaultdict(list)
    for q in every:
        c = pool_of(q)
        if c == "Tutorial":
            continue
        for m in q.monsters:
            if m["Type"]:
                rows[c].append((m["Nando_hp"], m["Nando_at"], m["Nando_etc"]))
    out = {}
    for i, name in enumerate(("hp", "at", "etc")):
        col = {"hp": 0, "at": 1, "etc": 2}[name]
        mult = lambda r: G.NANDO_ROWS[r][col]
        key = (lambda r: mult(r)) if name != "etc" else (lambda r: -mult(r))      # bigger = tougher
        lim = {}
        run = None
        for tier in ("LR", "HR", "G"):
            v = pct([r[i] for r in rows[tier]], 0.90)
            if run is not None and key(v) < key(run):
                v = run                                                  # keep the ladder monotone
            lim[tier] = run = v
        allrows = [r[i] for c, v in rows.items() for r in v]
        mx = max(allrows, key=key)
        lim["MAX"] = max(mx, lim["G"], key=key)
        out[name] = lim
    return out


def build_autofill(base, event, supp_dir):
    every = base + event
    small, supply = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for q in every:
        pl = pool_of(q)
        if pl in ("Tutorial",):
            continue
        sm = (q.get("main_zako1"), q.get("main_zako2"), q.get("zako_nando_hp"), q.get("zako_nando_at"),
              q.get("zako_nando_etc"))
        su = (q.get("item_set_no"), q.get("supp_set_no"), q.get("supp_time_flag"), q.get("supp_enemy_type"),
              q.get("supp_enemy_num"))
        for key in (f"{q.get('map')}|{pl}", f"*|{pl}"):
            small[key][sm] += 1
            supply[key][su] += 1
    def pack(counter, names):
        res = {}
        for key, c in counter.items():
            vals, n = c.most_common(1)[0]
            res[key] = dict(zip(names, vals), n=n, of=sum(c.values()))
        return res
    templates = []
    for q in every:
        pl = pool_of(q)
        if pl == "Tutorial" or not (q.reward1 or q.reward2):
            continue
        templates.append({
            "no": q.get("quest_no"), "name": q.get_text("name", 0), "map": q.get("map"), "pool": pl,
            "star": q.get("star"), "mons": [m["Type"] for m in q.monsters if m["Type"]],
            "r1": [list(r) for r in q.reward1], "r2": [list(r) for r in q.reward2],
        })
    used = {q.get("item_set_no") for q in every}
    present = set()
    if supp_dir and os.path.isdir(supp_dir):
        for f in os.listdir(supp_dir):
            if f.startswith("supp") and f.endswith(".supp"):
                present.add(int(f[4:7]))
    return {
        "small": pack(small, ("main_zako1", "main_zako2", "zako_nando_hp", "zako_nando_at", "zako_nando_etc")),
        "supply": pack(supply, ("item_set_no", "supp_set_no", "supp_time_flag", "supp_enemy_type",
                                 "supp_enemy_num")),
        "templates": templates,
        "spare_supp": sorted(n for n in present if n not in used and n > 0),
        "supp_present": sorted(present),
    }


def group_monster_defaults(base):
    """Most common Stamina / Sizeparam / Nando2 per rank group (applied with the 'Strength like' preset)."""
    t = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for q in base:
        k = group_key(q)
        if not k:
            continue
        for m in q.monsters:
            if m["Type"]:
                for f in ("Stamina", "Sizeparam", "Nando2"):
                    t[k][f][m[f]] += 1
    return {k: {f: c.most_common(1)[0][0] for f, c in d.items()} for k, d in t.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quests", required=True)
    ap.add_argument("--packs", default=None,
                    help="folder with PRISTINE quest1..quest4 (e.g. backups/original)")
    ap.add_argument("--supp", default=None, help="<romfs>/quest/support (lists the supply-box files)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    base = [Quest(open(f, "rb").read()) for f in sorted(glob.glob(os.path.join(a.quests, "q_*.quest")))]
    event = []
    if a.packs:
        for name in PACK_NAMES:
            p = os.path.join(a.packs, name)
            if os.path.isfile(p):
                event += [s.quest for s in EventPack(p).used_slots()]
    every = base + event

    groups = collections.defaultdict(list)
    for q in base:
        k = group_key(q)
        if k:
            groups[k].append(q)
    out_groups = {}
    for k, qs in groups.items():
        mons = [m for q in qs for m in q.monsters if m["Type"]]
        if not mons:
            continue
        med = lambda f: int(statistics.median_low(sorted(m[f] for m in mons)))
        hp, at, df = med("Nando_hp"), med("Nando_at"), med("Nando_etc")
        mq = lambda f: int(statistics.median_low(sorted(q.get(f) for q in qs)))
        out_groups[k] = {
            "quests": len(qs), "monsters": len(mons),
            "hp_row": hp, "at_row": at, "df_row": df,
            "hp": G.NANDO_ROWS[hp][0], "atk": G.NANDO_ROWS[at][1], "dmg": G.NANDO_ROWS[df][2],
            "fee": mq("contract"), "reward": mq("reward_money"), "hrp": mq("main_hrp"),
            "time": mq("time_min"),
            "fee_range": [min(q.get("contract") for q in qs), max(q.get("contract") for q in qs)],
            "reward_range": [min(q.get("reward_money") for q in qs), max(q.get("reward_money") for q in qs)],
            "hrp_range": [min(q.get("main_hrp") for q in qs), max(q.get("main_hrp") for q in qs)],
        }

    classes = ["Village", "Port LR", "Port HR", "Port G", "Event", "Grudge", "Challenge"]
    per_class = {}
    for f in MON_FIELDS:
        if f == "Type":
            continue
        t = collections.defaultdict(collections.Counter)
        for q in every:
            for m in q.monsters:
                if m["Type"]:
                    t[quest_class(q)][m[f]] += 1
        per_class[f] = {c: t[c].most_common(6) for c in classes if t[c]}
    for f in ("start_param", "prog_no", "hagi_no", "enemy_lv", "special_flag", "special_cond",
              "special_cond2", "supp_set_no", "supp_time_flag", "supp_enemy_type", "supp_enemy_num",
              "time_min", "failure_hrp", "demo_no"):
        t = collections.defaultdict(collections.Counter)
        for q in every:
            t[quest_class(q)][q.get(f)] += 1
        per_class[f] = {c: t[c].most_common(6) for c in classes if t[c]}

    common = {}
    for f in ("hagi_no", "prog_no", "enemy_lv", "demo_no", "special_flag", "special_cond",
              "special_cond2", "supp_set_no", "supp_time_flag", "supp_enemy_type", "supp_enemy_num",
              "start_param", "main_zako1", "main_zako2", "zako_nando_hp", "zako_nando_at",
              "zako_nando_etc", "time_min", "failure_hrp"):
        common[f] = collections.Counter(q.get(f) for q in base).most_common(6)

    examples = collections.defaultdict(list)
    for q in base:
        if q.get("special_flag"):
            key = f"{q.get('special_flag')}/{q.get('special_cond')}"
            if len(examples[key]) < 3:
                examples[key].append(q.get_text("name", 0))

    defaults = group_monster_defaults(base)
    for k, d in defaults.items():
        if k in out_groups:
            out_groups[k].update({"stamina": d["Stamina"], "sizeparam": d["Sizeparam"], "nando2": d["Nando2"]})
    tiers = build_tiers(every)
    auto = build_autofill(base, event, a.supp)
    with open(os.path.join(a.out, "autofill.json"), "w", encoding="utf-8") as f:
        json.dump(auto, f, separators=(",", ":"))

    data = {
        "tiers": tiers,
        "_about": "Generated by tools/build_benchmarks.py from the game's own quests "
                  f"({len(base)} base-game quests, {len(event)} event/challenge quests).",
        "base_quests": len(base), "event_quests": len(event),
        "groups": out_groups, "per_class": per_class, "common_values": common,
        "special_examples": examples,
    }
    with open(os.path.join(a.out, "benchmarks.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    print(f"{len(out_groups)} rank groups from {len(base)} quests (+{len(event)} event quests)")


if __name__ == "__main__":
    main()
