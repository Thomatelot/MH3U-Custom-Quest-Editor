"""Developer tool: the areas where each large monster has spawn positions on each map (em_mappos00
in arc/enemy/emXXX.arc) into data/spawn_areas.json. A start of your own (Monster pack) must use
one of these areas. Same data in the European and American versions.

    tools/build_spawn_areas.py <romfs folder>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mhqe import monsterpack as MP          # noqa: E402

game = MP.GameFiles(sys.argv[1])
out = {}
for em in range(1, 86):
    p = game.archive(em)
    if not p.is_file() or not MP.is_large(em):
        continue
    st = MP.MonsterData(p.read_bytes()).spawn.stages
    out[str(em)] = {str(s): sorted(int(a) for a in st[s]) for s in sorted(st)}
(ROOT / "data" / "spawn_areas.json").write_text(json.dumps({
    "_about": "Areas where each large monster has spawn positions (em_mappos00): monster -> internal stage -> "
              "areas (the numbering of start records, byte 9).",
    "areas": out}, separators=(",", ":")), encoding="utf-8")
print(len(out), "monsters")
