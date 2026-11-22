"""Build data/start_records.json: the monster start records as the game has them once it runs.

The start lists of code.bin (56-byte records, see monsterpack.py) hold the start position only at
run time: in the file, bytes +16..+43 of every record are zero, and one of the game's static
initialisers (run before main, listed in the table of relative offsets at the end of the code
segment) writes the position x, y, z, a 0, the facing and two more words there. This tool runs every
initialiser of that table in an emulator (unicorn, a developer tool only) and keeps, for each start
list of the placement table, its records as they are after start-up, plus the address range the
initialiser writes (the pack must never put anything there: it would be overwritten at boot).

    python tools/build_start_records.py <eu game folder> <us game folder>
(each folder holds romfs/ and exefs/code.bin)
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mhqe import monsterpack as MP  # noqa: E402

BASE = MP.BASE


def init_table(code: bytes, text_end: int) -> list[int]:
    """Functions of the table of relative offsets that ends the code segment."""
    def target(o):
        v = struct.unpack_from("<i", code, o)[0]
        t = o + BASE + v
        return t if BASE <= t < text_end and t % 4 == 0 else None
    o = text_end - BASE - 4
    while code[o:o + 4] == b"\0\0\0\0":
        o -= 4
    out = []
    while target(o) is not None:
        out.append(target(o))
        o -= 4
    return out[::-1]


def run_inits(code: bytes, inits: list[int]):
    from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_MEM_WRITE
    from unicorn.arm_const import (UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_C1_C0_2,
                                   UC_ARM_REG_FPEXC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                                   UC_ARM_REG_R3)
    mu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    mu.mem_map(BASE, 0x1000000)
    mu.mem_write(BASE, code)
    mu.mem_map(0x08000000, 0x200000)
    mu.mem_map(0xF0000000, 0x1000)
    mu.reg_write(UC_ARM_REG_C1_C0_2, mu.reg_read(UC_ARM_REG_C1_C0_2) | (0xF << 20))
    mu.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
    writer: dict[int, int] = {}
    cur = [0]

    def hook(_uc, _access, addr, size, _value, _ud):
        for k in range(size):
            writer.setdefault(addr + k, cur[0])
    mu.hook_add(UC_HOOK_MEM_WRITE, hook)
    failed = 0
    for f in inits:
        cur[0] = f
        mu.reg_write(UC_ARM_REG_SP, 0x081F0000)
        mu.reg_write(UC_ARM_REG_LR, 0xF0000000)
        for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3):
            mu.reg_write(r, 0)
        try:
            mu.emu_start(f, 0xF0000000, count=200000)
            failed += mu.reg_read(UC_ARM_REG_PC) != 0xF0000000
        except UcError:
            failed += 1
    return writer, bytes(mu.mem_read(BASE, len(code))), failed


def build(game_dir: Path) -> dict:
    game = MP.GameFiles(game_dir / "romfs")
    code = game.code
    tva = MP.find_placement_table(code, game.layout)
    place = MP.read_placement(code, tva)
    tva_text, _p, tsize = game.layout["text"]
    inits = init_table(code, tva_text + tsize)
    writer, mem, failed = run_inits(code, inits)
    arrays = sorted({p for lst in place.values() for _s, p in lst})
    out, lo, hi, writers = {}, None, None, set()
    for p in arrays:
        recs, _end = MP._records_at(code, p)
        o = p - BASE
        run = mem[o:o + 56 * len(recs)]
        for i in range(len(recs)):
            span = range(p + 56 * i + 16, p + 56 * i + 44)
            if not all(a in writer for a in span):
                raise SystemExit(f"record {i} of the list at 0x{p:X} is not written by an initialiser")
            writers |= {writer[a] for a in span}
            if run[56 * i:56 * i + 16] != recs[i][:16] or run[56 * i + 44:56 * i + 56] != recs[i][44:]:
                raise SystemExit(f"record {i} of the list at 0x{p:X} changes outside +16..+43")
        out[f"0x{p:X}"] = run.hex()
    lo = min(a for a in writer if writer[a] in writers)
    hi = max(a for a in writer if writer[a] in writers) + 1
    starts: dict = {}                             # stage -> area -> [monster], the one whose start point is copied first
    for em in sorted(place):
        for st, p in place[em]:
            for i in range(len(MP._records_at(code, p)[0])):
                r = bytes.fromhex(out[f"0x{p:X}"])[56 * i:56 * (i + 1)]
                odd = r[8] != 0xFF or not any(r[16:28])
                starts.setdefault(st, {}).setdefault(r[9], set()).add((odd, em))
    area_starts = {str(st): {str(a): [em for _odd, em in sorted(v)] for a, v in sorted(areas.items())}
                   for st, areas in sorted(starts.items())}
    return {"code_sha1": hashlib.sha1(code).hexdigest(), "placement_table": f"0x{tva:X}",
            "area_starts": area_starts,
            "initialiser": [f"0x{w:X}" for w in sorted(writers)], "written": [f"0x{lo:X}", f"0x{hi:X}"],
            "inits_run": len(inits), "inits_failed": failed, "arrays": out}


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    data = {"about": "Monster start lists of code.bin as they are once the game runs (bytes +16..+43 = "
                     "position x, y, z, 0, facing...: written at boot by a static initialiser). Built by "
                     "tools/build_start_records.py.", "regions": {}}
    for d in argv[1:]:
        game_dir = Path(d)
        region = MP.detect_region(game_dir / "romfs")
        data["regions"][region] = build(game_dir)
        r = data["regions"][region]
        print(region, len(r["arrays"]), "lists, initialiser", r["initialiser"], "writes", r["written"],
              f"({r['inits_run']} initialisers run, {r['inits_failed']} stopped early)")
    a = [r.pop("area_starts") for r in data["regions"].values()]
    if any(x != a[0] for x in a):
        raise SystemExit("the versions do not start their monsters in the same areas")
    data["area_starts"] = a[0]
    (ROOT / "data" / "start_records.json").write_text(json.dumps(data, indent=0), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
