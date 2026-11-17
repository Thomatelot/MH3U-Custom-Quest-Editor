"""Developer tool: data/monster_load.json, the unpacked size of each monster's archive
(romfs/arc/enemy/emNNN.arc, the same in the European and American versions) and the most monster
data that one quest of the game loads on each map (see mhqe/loadsize.py).

    tools/build_monster_load.py <romfs folder>
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mhqe import arc, loadsize                 # noqa: E402
from mhqe.project import RomSource             # noqa: E402

romfs = Path(sys.argv[1])
sizes = {}
for p in sorted((romfs / "arc" / "enemy").glob("em*.arc")):
    sizes[str(int(p.stem[2:]))] = sum(len(e.data) for e in arc.read(p).entries)

out = {"_about": "Unpacked size in bytes of each monster's archive (arc/enemy/emNNN.arc), and the most "
                 "monster data one quest of the game loads (large, small and roaming monsters) per quest map "
                 "and per kind of map (one area / several areas). Made by tools/build_monster_load.py.",
       "sizes": sizes, "maps": {}, "kinds": {}}
(ROOT / "data" / "monster_load.json").write_text(json.dumps(out), encoding="utf-8")
loadsize._data.cache_clear()

rom = RomSource(romfs, workspace=Path(tempfile.mkdtemp()), load_edits=False)
for no, q in sorted(rom.quests.items()):
    m, n = str(q.get("map")), loadsize.total(q)
    if n > out["maps"].get(m, {}).get("max", -1):
        out["maps"][m] = {"max": n, "quest": no}
for m, v in out["maps"].items():
    kind = "one_area" if int(m) in loadsize.ONE_AREA_MAPS else "areas"
    out["kinds"][kind] = max(out["kinds"].get(kind, 0), v["max"])
(ROOT / "data" / "monster_load.json").write_text(json.dumps(out, indent=0), encoding="utf-8")
for m, v in sorted(out["maps"].items(), key=lambda x: int(x[0])):
    print(m, f"{v['max'] / 1048576:.1f} MB", v["quest"])
print(out["kinds"])
