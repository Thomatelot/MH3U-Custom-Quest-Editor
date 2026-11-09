"""Developer tool: build data/lang/fr.json from numbered translation files.

tools/merge_fr.py <work dir>: for each keys_<name>.json (English texts, numbered) and
tr_<name>.json ({number: French text}) in the work dir, adds the pairs to data/lang/fr.json
(existing entries are kept unless replaced)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
work = Path(sys.argv[1])
out_path = ROOT / "data" / "lang" / "fr.json"
try:
    table = json.loads(out_path.read_text(encoding="utf-8"))
except (OSError, ValueError):
    table = {}
about = table.pop("_about", None)
n = 0
for tr in sorted(work.glob("tr_*.json")):
    name = tr.stem[3:]
    keys = json.loads((work / f"keys_{name}.json").read_text(encoding="utf-8"))
    for idx, fr in json.loads(tr.read_text(encoding="utf-8")).items():
        en = keys[int(idx)]
        if en.count("{}") != fr.count("{}"):
            print("placeholder mismatch, skipped:", name, idx, repr(en[:60]))
            continue
        table[en] = fr
        n += 1
extra = work / "extra.json"
if extra.is_file():
    table.update(json.loads(extra.read_text(encoding="utf-8")))
out = {"_about": about or "French texts of the editor: English text -> French text ({} = a variable part). "
                          "See mhqe/i18n.py."}
out.update(dict(sorted(table.items(), key=lambda kv: kv[0].lower())))
out_path.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
print(n, "pairs merged,", len(table), "entries in", out_path.name)
