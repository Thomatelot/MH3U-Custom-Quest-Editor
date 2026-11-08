"""Builds two data files from the game's own quests:

* data/spawn_lists.json   the small-monster spawn lists (the 45-byte records of the .quest_btl
                          files, and of the event quests' tails): one list per game quest.
* data/stray_sets.json    "Environment: Unstable" settings of every game quest on every map,
                          with the monsters the wiki lists for it (roaming monsters + small ones).

Usage:
    python tools/build_spawns.py --romfs <romfs> --packs <original quest1..4 folder> \
        --wiki <folder with the wiki .html pages> --out data
"""
from __future__ import annotations

import argparse
import base64
import glob
import html
import json
import os
import re
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mhqe import gamedata as G                      # noqa: E402
from mhqe.packs import EventPack                    # noqa: E402
from mhqe.quest import Quest                        # noqa: E402

REC = 45


def pool_of(q) -> str:
    no, star = q.get("quest_no"), q.get("star")
    if no >= 60000:
        return "Challenge" if no >= 61000 else "Grudge"
    if no >= 20000:
        return "Event"
    return "LR" if star <= 2 else "HR" if star <= 5 else "G"


def btl_records(path: str) -> list[bytes]:
    if not os.path.exists(path):
        return []
    d = open(path, "rb").read()
    if d[:4] != b"QTDB":
        return []
    n = struct.unpack_from("<I", d, 8)[0]
    return [d[12 + i * REC:12 + (i + 1) * REC] for i in range(n) if len(d) >= 12 + (i + 1) * REC]


def tail_records(q: Quest) -> list[bytes]:
    t = q.tail
    if len(t) < 25:
        return []
    n = struct.unpack_from("<I", t, 21)[0]
    return [t[25 + i * REC:25 + (i + 1) * REC] for i in range(n) if len(t) >= 25 + (i + 1) * REC]


def wiki_entries(folder: str) -> list[dict]:
    out = []
    for f in glob.glob(os.path.join(folder, "*.html")):
        t = open(f, encoding="utf8", errors="ignore").read()
        txt = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
        txt = html.unescape(re.sub(r"<[^>]+>", " ", txt))
        txt = re.sub(r"\s+", " ", txt)
        for m in re.finditer(
                r"([^:]{3,80}?) Main Goal :(.*?)Locale: ([^:]*?) Time Limit: (\d+) min\. Environment: (\w+) "
                r"Reward: (\d+)z HR Points: (\d+) Contract Fee: (\d+)z Monsters: (.*?)"
                r"(?: Description:| Notes:| Key Quest| Urgent Quest| [^:]{3,80}? Main Goal :|$)", txt):
            out.append(dict(env=m.group(5), reward=int(m.group(6)), hrp=int(m.group(7)),
                            fee=int(m.group(8)), mons=m.group(9)))
    return out


def names_in(text: str) -> list[int]:
    """Monster ids named in a wiki 'Monsters:' cell, in order, longest names first."""
    keys = sorted(((re.sub(r"[^a-z0-9]", "", n.lower()), i) for i, n in G.MONSTERS.items()),
                  key=lambda x: -len(x[0]))
    out = []
    for part in re.split(r"\s*,\s*|\s+and\s+", text):
        p = re.sub(r"[^a-z0-9]", "", part.lower())
        for k, i in keys:
            if p == k or (p and p.startswith(k) and len(p) - len(k) <= 12):
                if i not in out:
                    out.append(i)
                break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--romfs", required=True)
    ap.add_argument("--packs", required=True)
    ap.add_argument("--wiki", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    quests = {}
    for f in sorted(glob.glob(os.path.join(a.romfs, "quest", "eu", "q_*.quest"))):
        q = Quest(open(f, "rb").read())
        recs = btl_records(os.path.join(a.romfs, "quest", "btl", os.path.basename(f) + "_btl"))
        quests[q.get("quest_no")] = (q, recs)
    for n in ("quest1", "quest2", "quest3", "quest4"):
        for s in EventPack(os.path.join(a.packs, n)).used_slots():
            q = s.quest
            quests[q.get("quest_no")] = (q, tail_records(q))

    lists = []
    for no, (q, recs) in sorted(quests.items()):
        if not recs:
            continue
        raw = b"".join(recs)
        lists.append({"no": no, "name": q.get_text("name", 0), "map": q.get("map"), "star": q.get("star"),
                      "pool": pool_of(q), "main": [q.get("main_zako1"), q.get("main_zako2")],
                      "n": len(recs), "z": base64.b64encode(zlib.compress(raw, 9)).decode()})
    out = Path(a.out)
    (out / "spawn_lists.json").write_text(json.dumps(
        {"_about": "small-monster spawn records (45 bytes each) of every game quest that has them",
         "lists": lists}, separators=(",", ":")), encoding="utf-8")
    print("spawn lists:", len(lists))

    ent = wiki_entries(a.wiki)
    by = {}
    for e in ent:
        by.setdefault((e["reward"], e["hrp"], e["fee"]), []).append(e)
    sets = []
    for no, (q, _r) in sorted(quests.items()):
        if q.get("nora_set_per") <= 0 and q.get("nora_set_type") != 1:
            pass
        cand = by.get((q.get("reward_money"), q.get("main_hrp"), q.get("contract")), [])
        envs = {c["env"] for c in cand}
        mons = names_in(cand[0]["mons"]) if cand and len(envs) <= 1 else []
        own = {m["Type"] for m in q.monsters if m["Type"]}
        sets.append({"no": no, "name": q.get_text("name", 0), "map": q.get("map"), "star": q.get("star"),
                     "pool": pool_of(q),
                     "type": q.get("nora_set_type"), "per": q.get("nora_set_per"),
                     "ptype": q.get("nora_per_type"), "max": q.get("nora_set_max"),
                     "table": q.get("nora_set_table"), "pekko": q.get("nora_pekko"),
                     "wiki_env": (envs.pop() if len(envs) == 1 else ""),
                     "mons": [m for m in mons if m not in own]})
    (out / "stray_sets.json").write_text(json.dumps(
        {"_about": "nora_* (roaming monsters) settings of every game quest; 'mons' = other monsters the wiki lists",
         "quests": sets}, separators=(",", ":")), encoding="utf-8")
    print("stray sets:", len(sets), "unstable:", sum(1 for s in sets if s["per"] > 0))


if __name__ == "__main__":
    main()
