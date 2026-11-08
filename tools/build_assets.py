"""Developer/CLI wrapper: rebuild the editor's pictures from YOUR extracted game.

    python tools/build_assets.py --romfs <romfs folder> [--code <exefs/code.bin>] [--wiki <saved wiki pages>]

The same thing is available in the editor: Settings > Rebuild the pictures from my game.
Needs Pillow (pip install pillow). See mhqe/artbuild.py for what is read from the game.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mhqe import artbuild  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--romfs", required=True, help="the game's extracted romfs folder")
    ap.add_argument("--code", default=None, help="exefs/code.bin (item icons); found next to romfs if omitted")
    ap.add_argument("--wiki", default=None, help="optional: saved wiki pages, to double-check the monster icons")
    ap.add_argument("--out", default=str(artbuild.ROOT), help="editor folder (default: this one)")
    a = ap.parse_args()
    code = a.code or artbuild.default_code_bin(a.romfs)
    try:
        artbuild.build(a.romfs, a.out, code=code, wiki=a.wiki)
    except artbuild.ArtError as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
