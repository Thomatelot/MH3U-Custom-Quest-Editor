"""Builds data/start_usage.json: for every map and every 'Starttype' value (the start position of
a large monster) which monsters the game's own quests start there. Used by the start-position
dialog of the editor. Usage:

    python tools/build_start_usage.py --quests <romfs/quest/eu> --packs <original quest1..4 folder> --out data
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mhqe.packs import EventPack          # noqa: E402
from mhqe.quest import Quest              # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quests", required=True)
    ap.add_argument("--packs", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    quests = [Quest(open(f, "rb").read()) for f in sorted(glob.glob(os.path.join(a.quests, "q_*.quest")))]
    for n in ("quest1", "quest2", "quest3", "quest4"):
        quests += [s.quest for s in EventPack(os.path.join(a.packs, n)).used_slots()]
    table: dict = defaultdict(lambda: defaultdict(list))
    for q in quests:
        name = q.get_text("name", 0)
        for m in q.monsters:
            if m["Type"]:
                table[q.get("map")][m["Starttype"]].append([m["Type"], q.get("quest_no"), name])
    out = {}
    for mp, pos in sorted(table.items()):
        out[str(mp)] = {}
        for s, rows in sorted(pos.items()):
            seen, ex = set(), []
            for em, no, name in rows:                    # one example per monster, up to 6
                if em not in seen and len(ex) < 6:
                    seen.add(em)
                    ex.append([em, no, name])
            out[str(mp)][str(s)] = {"n": len(rows), "ex": ex}
    path = Path(a.out) / "start_usage.json"
    path.write_text(json.dumps({"_about": "map -> Starttype -> how many game monsters start there, with examples",
                                "maps": out}, indent=0), encoding="utf-8")
    print("wrote", path, sum(len(v) for v in out.values()), "entries")


if __name__ == "__main__":
    main()
