"""Custom supply boxes.

A quest does not contain its supply box. It only holds a *number* (``item_set_no``) and the game
loads ``romfs/quest/support/suppNNN.supp`` (472 bytes: 40 item slots + 40 quantities). To give a
quest a box of your own choosing the editor therefore

  1. picks one of the game's supply files that NO quest of the game uses (data/autofill.json,
     ``spare_supp``; there are 10 of them),
  2. writes your item list into a replacement file for that number, and
  3. points the quest at that number.

The replacement is a normal romfs mod (``quest/support/suppNNN.supp``): Citra's ``load/mods`` or
Luma's ``luma/titles/<id>/romfs``. Without the mod the game simply loads the original file of that
number, so a quest is never left without a box.

File layout (checked on all 196 supply files of the EU game):
  0x00 'XFS\\0' header and class names, identical in every file
  0x90 u32 = 40, 0x94 .. 0x133 : 40 x u32 item id      (0 = empty slot)
  0x134 u32 = 40, 0x138 .. 0x1D7: 40 x u32 quantity     (1..99)
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from . import gamedata as G

SLOTS = 40
MAX_QTY = 99
TYPES_AT, NUMS_AT, SIZE = 0x94, 0x138, 472
_TEMPLATE = G.DATA_DIR / "supp_template.bin"

try:
    _AUTO = json.loads((G.DATA_DIR / "autofill.json").read_text(encoding="utf-8"))
except (OSError, ValueError):
    _AUTO = {}
SPARE: list[int] = list(_AUTO.get("spare_supp", []))


class SuppError(ValueError):
    pass


def check_items(items) -> list[tuple[int, int]]:
    out = []
    for iid, qty in items:
        iid, qty = int(iid), int(qty)
        if not (0 < iid < len(G.ITEMS)):
            raise SuppError(f"unknown item id {iid}")
        if not 1 <= qty <= MAX_QTY:
            raise SuppError(f"{G.item_name(iid)}: quantity must be between 1 and {MAX_QTY}")
        out.append((iid, qty))
    if len(out) > SLOTS:
        raise SuppError(f"a supply box holds at most {SLOTS} item slots")
    return out


def build_supp(items) -> bytes:
    """The bytes of a suppNNN.supp holding ``items`` = [(item id, quantity), ...] (one per slot)."""
    items = check_items(items)
    try:
        data = bytearray(_TEMPLATE.read_bytes())
    except OSError as exc:
        raise SuppError(f"template missing: {exc}") from None
    if len(data) != SIZE:
        raise SuppError("template has an unexpected size")
    types = [0] * SLOTS
    nums = [0] * SLOTS
    for i, (iid, qty) in enumerate(items):
        types[i], nums[i] = iid, qty
    struct.pack_into(f"<{SLOTS}I", data, TYPES_AT, *types)
    struct.pack_into(f"<{SLOTS}I", data, NUMS_AT, *nums)
    return bytes(data)


def read_supp(data: bytes) -> list[tuple[int, int]]:
    if len(data) != SIZE or data[:3] != b"XFS":
        raise SuppError("not a supply file")
    types = struct.unpack_from(f"<{SLOTS}I", data, TYPES_AT)
    nums = struct.unpack_from(f"<{SLOTS}I", data, NUMS_AT)
    return [(t, n) for t, n in zip(types, nums) if t]


def game_box(no: int) -> list[tuple[int, int]] | None:
    """Slots of the game's own box number ``no`` (None if the game has no such file)."""
    items = G.SUPP_SETS.get(no)
    if items is None:
        return None
    return [(i, q) for i, q in items]


class CustomBoxes:
    """The custom boxes of this installation: {number: [(item, qty), ...]} and their names, kept in
    a small JSON file next to the program and written out as supply files on request."""

    NAME_MAX = 40

    def __init__(self, path: Path):
        self.path = Path(path)
        self.boxes: dict[int, list[tuple[int, int]]] = {}
        self.names: dict[int, str] = {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for k, v in raw.get("boxes", {}).items():
                self.boxes[int(k)] = [(int(a), int(b)) for a, b in v]
            for k, v in raw.get("names", {}).items():
                if int(k) in self.boxes and str(v).strip():
                    self.names[int(k)] = str(v).strip()[:self.NAME_MAX]
        except (OSError, ValueError, TypeError, AttributeError):
            self.boxes, self.names = {}, {}
        for no in sorted(self.boxes):                   # box files without names get a default name
            self.names.setdefault(no, self.default_name())

    # ----------------------------------------------------------------- state
    def is_custom(self, no: int) -> bool:
        return no in self.boxes

    def items(self, no: int) -> list[tuple[int, int]]:
        return list(self.boxes.get(no, []))

    def numbers(self) -> list[int]:
        return sorted(self.boxes)

    def name(self, no: int) -> str:
        return self.names.get(no) or f"My box {no}"

    def default_name(self) -> str:
        used = {n.lower() for n in self.names.values()}
        k = 1
        while f"my box {k}" in used:
            k += 1
        return f"My box {k}"

    def free_number(self, in_use: set[int]) -> int | None:
        """A spare number that no quest of yours uses and that holds no custom box yet."""
        for n in SPARE:
            if n not in in_use and n not in self.boxes:
                return n
        return None

    def available(self, in_use: set[int]) -> int:
        return sum(1 for n in SPARE if n not in in_use and n not in self.boxes)

    # ---------------------------------------------------------------- change
    def set_items(self, no: int, items) -> None:
        if no not in SPARE:
            raise SuppError(f"number {no} is not one of the spare supply numbers")
        self.boxes[no] = check_items(items)
        self.names.setdefault(no, self.default_name())
        self.save()

    def set_name(self, no: int, name: str) -> None:
        name = " ".join(str(name).split())[:self.NAME_MAX]
        if no not in self.boxes:
            raise SuppError("this is not one of your boxes")
        if not name:
            raise SuppError("a box needs a name")
        if any(n.lower() == name.lower() for k, n in self.names.items() if k != no):
            raise SuppError(f"another box is already called '{name}'")
        self.names[no] = name
        self.save()

    def release(self, no: int) -> None:
        if self.boxes.pop(no, None) is not None:
            self.names.pop(no, None)
            self.save()

    def save(self) -> None:
        payload = {"_about": "Custom supply boxes: number -> [[item id, quantity], ...]; names: number -> name",
                   "boxes": {str(k): [list(x) for x in v] for k, v in sorted(self.boxes.items())},
                   "names": {str(k): v for k, v in sorted(self.names.items())}}
        self.path.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    # ---------------------------------------------------------------- export
    def export(self, romfs_dir: Path, keep=None) -> list[Path]:
        """Write quest/support/suppNNN.supp for the boxes in ``keep`` (default: all)."""
        out = []
        folder = Path(romfs_dir) / "quest" / "support"
        folder.mkdir(parents=True, exist_ok=True)
        for no in sorted(self.boxes):
            if keep is not None and no not in keep:
                continue
            p = folder / f"supp{no:03d}.supp"
            p.write_bytes(build_supp(self.boxes[no]))
            out.append(p)
        return out


def file_name(no: int) -> str:
    return f"supp{no:03d}.supp"


def installed_files(romfs_dirs) -> dict[int, list[Path]]:
    """{number: [files]} of the supply files that sit in the given romfs mod folders under one of the
    spare numbers (the only numbers this editor ever writes)."""
    out: dict[int, list[Path]] = {}
    for root in romfs_dirs:
        folder = Path(root) / "quest" / "support"
        for no in SPARE:
            f = folder / file_name(no)
            if f.is_file():
                out.setdefault(no, []).append(f)
    return out


def file_state(files, items) -> str:
    """'missing' | 'same' | 'older' for the installed copies of a box holding ``items``."""
    if not files:
        return "missing"
    try:
        want = build_supp(items)
        return "same" if all(Path(f).read_bytes() == want for f in files) else "older"
    except (OSError, SuppError):
        return "older"
