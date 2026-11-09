"""Write data/map_zones.json: where each area of each quest map sits on the 3DS map picture.

Source: mh3u-quest-studio (Matt Wood, MIT licence, see THIRD_PARTY.md), data/art_layout.json,
"map_markers": the centre of each map-numbered area on the Wii U's 512 x 512 area maps. The 3DS
map textures (td_map_*, 256 x 256) hold the same drawing at one third of that size, at the same
origin; this was checked on every map against the coloured areas of the 3DS pictures (average
distance under 1.5 pixels on the large maps). Quest map 9 (the land Arena variant) has no Wii U
entry; its two points were read off the 3DS picture.

usage: python tools/build_map_zones.py path/to/mh3u-quest-studio/data/art_layout.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# quest map id (this editor) -> internal stage of the studio's table
QUEST_TO_STAGE = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 10: 9, 11: 10, 12: 11, 13: 12, 14: 13, 15: 14}
EXTRA = {9: {"0": [55.0, 102.0], "1": [95.0, 68.0]}}

layout = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["map_markers"]
maps = {}
for q, st in QUEST_TO_STAGE.items():
    pts = layout.get(str(st))
    if pts:
        maps[str(q)] = {k: [round(x / 3, 1), round(y / 3, 1)] for k, (x, y) in
                        sorted(pts.items(), key=lambda kv: int(kv[0]))}
for q, pts in EXTRA.items():
    maps[str(q)] = pts
maps = dict(sorted(maps.items(), key=lambda kv: int(kv[0])))
out = {"_about": "Centre of each area (number painted on the map, 0 = camp) on the 3DS map picture "
                 "td_map_* (256 x 256 pixels), per quest map id. From mh3u-quest-studio (Matt Wood, MIT "
                 "licence, see THIRD_PARTY.md), scaled from the Wii U maps; see tools/build_map_zones.py.",
       "maps": maps}
text = "{\n \"_about\": " + json.dumps(out["_about"]) + ",\n \"maps\": {\n" + ",\n".join(
    f"  {json.dumps(q)}: {json.dumps(v, separators=(',', ':'))}" for q, v in maps.items()) + "\n }\n}\n"
json.loads(text)
(ROOT / "data" / "map_zones.json").write_text(text, encoding="utf-8")
print(len(maps), "maps")
