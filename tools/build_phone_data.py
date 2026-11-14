"""Build android/web/data.js: the lists the phone notebook needs (monsters, maps, items,
star-rank presets...), taken from the editor's own tables so both always agree.

Run from the repository root:  python tools/build_phone_data.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mhqe import catalog as C          # noqa: E402
from mhqe import gamedata as G         # noqa: E402
from mhqe import helptext as H         # noqa: E402
from mhqe import rules                 # noqa: E402


def hidden_item(name: str) -> bool:     # same rule as picker._hidden_item
    return (not name or name.startswith("(None)") or name.startswith("(Rien)") or "DUMMY" in name
            or "(dup" in name or name.startswith("item #"))


def main() -> None:
    fr = json.loads((G.DATA_DIR / "lang" / "names_fr.json").read_text(encoding="utf-8"))
    icons = json.loads((G.DATA_DIR / "icons.json").read_text(encoding="utf-8"))
    monsters = []
    for em, name in G.MONSTERS.items():
        cls = C.MONSTER_CLASS.get(em, "Other")
        monsters.append({"id": em, "en": name, "fr": fr["monsters"].get(str(em), name), "cls": cls,
                         "threat": C.MONSTER_THREAT.get(em, 0), "maps": G.maps_for_monster(em),
                         "icon": icons["monsters"].get(str(em))})
    maps = [{"id": m, "en": n, "fr": fr["maps"].get(str(m), n), "img": icons["maps"].get(str(m))}
            for m, n in G.MAP_NAMES.items()]
    items = []
    for iid, name in enumerate(G.ITEMS):
        if hidden_item(name):
            continue
        frn = fr["items"][iid] if iid < len(fr["items"]) else name
        items.append([iid, name, frn if not hidden_item(frn) else name, icons["items"].get(str(iid))])
    groups = []
    for key in H.group_keys():
        g = H.GROUPS[key]
        hub, star = key.split()
        groups.append({"key": key, "hub": hub, "star": int(star), "label": H.group_label(key),
                       "fee": g["fee"], "reward": g["reward"], "hrp": g["hrp"], "time": g.get("time", 50)})
    data = {
        "version": 1,
        "monsters": monsters,
        "classes": list(C.MONSTER_CLASSES),
        "maps": maps,
        "items": items,
        "groups": groups,
        "sizes": [[label, size] for label, size, _spread in H.SIZE_PRESETS],
        "ranks": [[k, v] for k, v in rules.MONSTER_RANKS.items()],
        "hr": [n for n in rules.HR_CHOICES[1:]],
        "day_only_maps": sorted(rules.DAY_ONLY_MAPS),
        "sprites": {"monster_columns": icons["monster_columns"], "item_cell": icons["item_cell"],
                    "item_columns": icons["item_columns"]},
    }
    out = ROOT / "android" / "web" / "data.js"
    out.write_text("// Built by tools/build_phone_data.py. Do not edit.\nconst DATA = "
                   + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"{out}: {out.stat().st_size:,} bytes, {len(monsters)} monsters, {len(items)} items")


if __name__ == "__main__":
    main()
