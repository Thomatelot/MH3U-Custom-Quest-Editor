"""Write data/lang/names_fr.json: the game's own French names of items, monsters and maps.

Read from the French text files of the game (romfs/arc/ID/ID_com_fre.arc: GUI\\font\\Item00_fre and
Monster_fre, same order as the English ones the editor already uses). Slots the game leaves as
DUMMY keep the editor's English names. Map names are written by hand from the game's lobby texts
(CardEdit_fre), where some are cut short.

usage: python tools/build_fr_names.py <romfs folder>
"""
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mhqe.artbuild import arc_entries  # noqa: E402

GMD = 0x242BB29A
ENGLISH_MAPS = {1: "Deserted Island", 2: "Sandy Plains", 3: "Flooded Forest", 4: "Tundra", 5: "Volcano",
                13: "Misty Peaks"}
MAPS_FR = {1: "Île déserte", 2: "Plaines de sable", 3: "Forêt inondée", 4: "Toundra", 5: "Volcan",
           6: "Grand désert", 7: "Ruines englouties", 8: "Arène", 9: "Arène (variante)",
           10: "Arène aquatique (variante)", 11: "Terre sacrée", 12: "Arène aquatique", 13: "Pics brumeux",
           14: "Tour", 15: "Mer impure"}


def strings(arc, entry):
    for name, th, raw, off, cs in arc_entries(arc):
        if th == GMD and name == entry:
            d = zlib.decompress(raw[off:off + cs])
            n, _labels, size = struct.unpack_from("<III", d, 16)
            return [s.decode("utf-8") for s in d[len(d) - size:].split(b"\0")[:n]]
    raise SystemExit(f"{entry} not found in {arc}")


romfs = Path(sys.argv[1])
arc_fr = romfs / "arc" / "ID" / "ID_com_fre.arc"
arc_en = romfs / "arc" / "ID" / "ID_com_eng.arc"
items_en_game = strings(arc_en, "GUI\\font\\Item00_eng")
items_fr_game = strings(arc_fr, "GUI\\font\\Item00_fre")
mons_fr = strings(arc_fr, "GUI\\font\\Monster_fre")
ours = json.loads((ROOT / "data" / "items_en.json").read_text(encoding="utf-8"))["items"]
monsters = json.loads((ROOT / "data" / "monsters.json").read_text(encoding="utf-8"))["monsters"]
items = []
for i, en in enumerate(ours):
    fr = items_fr_game[i] if i < len(items_fr_game) else ""
    game_en = items_en_game[i] if i < len(items_en_game) else ""
    items.append(fr if fr and "DUMMY" not in fr and game_en == en else en)
QUALIFIERS = {"Blue": "bleu", "Red": "rouge", "Green/Brown": "vert/brun", "Underwater": "sous l'eau"}
SPECIAL = {71: "Deviljho sauvage"}          # the game names it "Deviljho" too
mon = {}
for k, v in monsters.items():
    i = int(k)
    if i in SPECIAL:
        mon[k] = SPECIAL[i]
        continue
    if i < len(mons_fr) and mons_fr[i] not in ("", "NO_DATA") and "DUMMY" not in mons_fr[i]:
        fr = mons_fr[i]
        en = v["name"]
        if "(" in en and "(" not in fr:              # game text has no variant: keep the editor's detail
            q = en[en.index("(") + 1:en.rindex(")")]
            fr += f" ({QUALIFIERS.get(q, MAPS_FR.get(next((m for m, n in ENGLISH_MAPS.items() if n == q), 0), q))})"
        mon[k] = fr
out = {"_about": "French names from the game's own text (ID_com_fre.arc); see tools/build_fr_names.py.",
       "items": items, "monsters": mon, "maps": {str(k): v for k, v in MAPS_FR.items()}}
(ROOT / "data" / "lang").mkdir(parents=True, exist_ok=True)
(ROOT / "data" / "lang" / "names_fr.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                                                      encoding="utf-8")
print(len(items), "items,", len(mon), "monsters,", sum(1 for a, b in zip(items, ours) if a != b), "items translated")
