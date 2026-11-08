"""Build the monster placement pack (ROM hack) from an extracted MH3U, without the editor window.

    python tools/build_monster_pack.py --romfs <extracted game>/romfs --out <folder>

The output folder holds romfs/, exefs/code.ips and mhqe_monster_pack.json: copy its content into
<Citra>/load/mods/<title id>/ (Citra) or luma/titles/<title id>/ (3DS with Luma). Title ids:
00040000000B1D00 (EU), 00040000000AE400 (US). See mhqe/monsterpack.py for what it changes.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mhqe import gamedata as G          # noqa: E402
from mhqe import monsterpack            # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--romfs", required=True, help="romfs folder of the extracted game (exefs/ next to it)")
    ap.add_argument("--out", required=True, help="output folder (replaced)")
    a = ap.parse_args()
    man = monsterpack.build(a.romfs, a.out)
    region = man.get("region")
    print(f"Version: {G.region_name(region)}. Install: copy the content of {a.out} into "
          f"load/mods/{man.get('title_id')}/ (Citra) or luma/titles/{man.get('title_id')}/ (Luma).")


if __name__ == "__main__":
    main()
