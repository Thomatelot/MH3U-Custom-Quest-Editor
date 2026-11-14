"""Developer tool: read the roaming-monster lists, the start 'forms' and the quest list from
the game's code.bin into data/roaming_tables.json, data/start_forms.json, data/master_quests.json.

    tools/build_code_tables.py <romfs folder>     (exefs/code.bin next to it)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mhqe import gamecode as GC, monsterpack as MP          # noqa: E402

game = MP.GameFiles(sys.argv[1])
code = game.code
tables = GC.roaming_tables(code)
(ROOT / "data" / "roaming_tables.json").write_text(json.dumps({
    "_about": "Roaming-monster lists of the game (code.bin), index = the quest field nora_set_table. "
              "Entry fields: " + ", ".join(GC.ROAM_FIELDS),
    "free_slots": GC.free_roaming_slots(code),
    "tables": {str(k): v for k, v in sorted(tables.items())}}, separators=(",", ":")), encoding="utf-8")
place = MP.read_placement(code, MP.find_placement_table(code, game.layout))
forms = {}
for em, lst in place.items():
    for st, ptr in lst:
        f = GC.start_forms(code, ptr)
        if any(f):
            forms.setdefault(str(em), {})[str(st)] = f
(ROOT / "data" / "start_forms.json").write_text(json.dumps({
    "_about": "Byte 11 of the game's start records: the 'form' a monster is given when it appears "
              "(monster -> internal stage -> one value per start position). Only non-zero lists.",
    "forms": forms}, separators=(",", ":")), encoding="utf-8")
_off, lst = GC.find_master_list(code)
(ROOT / "data" / "master_quests.json").write_text(json.dumps({
    "_about": "Quest numbers the game can mark as cleared (code.bin quest list), and how many slots are unused.",
    "numbers": sorted(n for n in lst if n), "free": len(GC.free_master_slots(lst))},
    separators=(",", ":")), encoding="utf-8")
print(len(tables), "roaming lists,", sum(len(v) for v in forms.values()), "start lists with forms,",
      len([n for n in lst if n]), "quests in the list")
