"""Write data/equipment.json and data/lang/equipment_fr.json: the game's names of weapons, armor,
talismans and skill trees (index == the id the game stores), read from its own text files
(romfs/arc/ID/ID_arena_eng.arc and ID_arena_fre.arc).

usage: python tools/build_equipment.py <romfs folder>
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
FILES = {7: "Lsword", 8: "Sword", 9: "Hammer", 10: "Lance", 11: "Hbg", 13: "Lbg", 14: "Lsword2", 15: "Axe",
         16: "Gunlance", 17: "Bow", 18: "WSword", 19: "Pipe", 1: "Body", 2: "Arm", 3: "Waist", 4: "Leg",
         5: "Helm", 6: "Acce"}
TYPES = {"en": {1: "Chest", 2: "Arms", 3: "Waist", 4: "Legs", 5: "Head", 6: "Talisman", 7: "Great Sword",
                8: "Sword & Shield", 9: "Hammer", 10: "Lance", 11: "Heavy Bowgun", 13: "Light Bowgun",
                14: "Long Sword", 15: "Switch Axe", 16: "Gunlance", 17: "Bow", 18: "Dual Blades",
                19: "Hunting Horn"},
         "fr": {1: "Torse", 2: "Bras", 3: "Taille", 4: "Jambes", 5: "Tête", 6: "Talisman", 7: "Grande épée",
                8: "Épée et bouclier", 9: "Marteau", 10: "Lance", 11: "Fusarbalète lourd",
                13: "Fusarbalète léger", 14: "Épée longue", 15: "Morpho-hache", 16: "Lancecanon", 17: "Arc",
                18: "Lames doubles", 19: "Corne de chasse"}}


def gmds(arc):
    out = {}
    for name, th, raw, off, cs in arc_entries(arc):
        if th == GMD:
            d = zlib.decompress(raw[off:off + cs])
            n, _labels, size = struct.unpack_from("<III", d, 16)
            out[name.rsplit("\\", 1)[-1]] = [s.decode("utf-8") for s in d[len(d) - size:].split(b"\0")[:n]]
    return out


romfs = Path(sys.argv[1])
for lang, code in (("en", "eng"), ("fr", "fre")):
    g = gmds(romfs / "arc" / "ID" / f"ID_arena_{code}.arc")
    names = {}
    for t, f in FILES.items():
        lst = list(g[f"{f}_{code}"])
        lst[0] = "(none)" if lang == "en" else "(aucun)"
        names[str(t)] = lst
    skills = list(g[f"Skill_Type_{code}"])
    skills[0] = "(none)" if lang == "en" else "(aucun)"
    out = {"_about": "Names from the game's own text (ID_arena_" + code + ".arc), index = the id the game "
                     "stores; see tools/build_equipment.py.",
           "types": {str(k): v for k, v in TYPES[lang].items()}, "names": names, "skills": skills}
    path = ROOT / "data" / ("equipment.json" if lang == "en" else "lang/equipment_fr.json")
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(path.name, sum(len(v) for v in names.values()), "names,", len(skills), "skills")
