"""Event / challenge quest packs (the ``quest1`` .. ``quest4`` files).

On the 3DS they live in the game's extdata::

    <sdmc>/Nintendo 3DS/<id0>/<id1>/extdata/00000000/00000B1D/user/quest1 .. quest4

Layout (167 936 bytes, verified on the EU game):

    0x0000  u32 header value (0x2C in every pack, kept verbatim)
    0x0004  20 slots of 0x2010 bytes:
              +0x0000  quest record ('QTDS'), zero padded to 0x2000
              +0x2000  16-byte file name, e.g. 'q_20102.quest'
    ....    zero padding up to the end of the file

An empty slot is all zeros.
"""
from __future__ import annotations

from pathlib import Path

from .quest import MAGIC, Quest, QuestFormatError

HEADER = 4
SLOT = 0x2010
DATA = 0x2000
NAME = 16
SLOTS = 20
PACK_SIZE = 0x29000
PACK_NAMES = ("quest1", "quest2", "quest3", "quest4")


class PackError(ValueError):
    pass


def fit_record(data: bytes, size: int = DATA) -> bytes:
    """Pad / trim a record to exactly *size* bytes (only zero padding is trimmed)."""
    data = bytes(data)
    if len(data) <= size:
        return data + bytes(size - len(data))
    if any(data[size:]):
        raise PackError(
            f"the quest is {len(data.rstrip(bytes(1)))} bytes long but a slot "
            f"holds {size}: shorten the texts (about {len(data.rstrip(bytes(1))) - size} "
            f"bytes too many)")
    return data[:size]


def file_name_for(quest_no: int) -> str:
    return f"q_{quest_no:05d}.quest"


class Slot:
    """One of the 20 slots of a pack."""

    def __init__(self, index: int, raw: bytes):
        self.index = index
        self.raw = bytes(raw)                    # original 0x2010 bytes
        self.dirty = False
        self.quest: Quest | None = None
        self.filename = ""
        if raw[:4] == MAGIC:
            self.quest = Quest(raw[:DATA])
            self.filename = raw[DATA:DATA + NAME].split(b"\0", 1)[0].decode("ascii", "replace")
        elif any(raw):
            raise PackError(f"slot {index + 1} contains data that is not a quest")

    @property
    def empty(self) -> bool:
        return self.quest is None

    def serialize(self) -> bytes:
        if not self.dirty:
            return self.raw
        if self.quest is None:
            return bytes(SLOT)
        rec = fit_record(self.quest.to_bytes(), DATA)
        name = self.filename.encode("ascii")
        if len(name) >= NAME:
            raise PackError(f"file name too long: {self.filename!r}")
        return rec + name + bytes(NAME - len(name))


class EventPack:
    """One pack file (quest1..quest4) held in memory."""

    def __init__(self, path: str | Path, data: bytes | None = None):
        self.path = Path(path)
        raw = bytes(self.path.read_bytes() if data is None else data)
        if len(raw) < HEADER + SLOTS * SLOT:
            raise PackError(f"{self.path.name}: {len(raw)} bytes is too small for a quest pack")
        self.header = raw[:HEADER]
        self.tail = raw[HEADER + SLOTS * SLOT:]
        self.slots = [Slot(i, raw[HEADER + i * SLOT:HEADER + (i + 1) * SLOT])
                      for i in range(SLOTS)]

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def dirty(self) -> bool:
        return any(s.dirty for s in self.slots)

    def used_slots(self) -> list[Slot]:
        return [s for s in self.slots if not s.empty]

    def free_slots(self) -> list[Slot]:
        return [s for s in self.slots if s.empty]

    def mark_dirty(self, slot: int) -> None:
        self.slots[slot].dirty = True

    def create_quest(self, slot: int, template: Quest, quest_no: int) -> Quest:
        s = self.slots[slot]
        if not s.empty:
            raise PackError(f"slot {slot + 1} of {self.name} is not empty")
        q = template.copy()
        q.pad_to(DATA)                               # a base-game quest file is shorter than an event slot
        q.set("quest_no", quest_no)
        fit_record(q.to_bytes(), DATA)               # raises if it cannot fit
        s.quest = q
        s.filename = file_name_for(quest_no)
        s.dirty = True
        return q

    def clear_slot(self, slot: int) -> None:
        s = self.slots[slot]
        s.quest = None
        s.filename = ""
        s.dirty = True

    def set_quest_no(self, slot: int, quest_no: int) -> None:
        s = self.slots[slot]
        s.quest.set("quest_no", quest_no)
        s.filename = file_name_for(quest_no)
        s.dirty = True

    def to_bytes(self) -> bytes:
        return self.header + b"".join(s.serialize() for s in self.slots) + self.tail

    def validate_fit(self) -> list[str]:
        """Return a message for every slot whose quest no longer fits."""
        problems = []
        for s in self.slots:
            if s.quest is not None:
                try:
                    fit_record(s.quest.to_bytes(), DATA)
                except PackError as exc:
                    problems.append(f"{self.name} slot {s.index + 1}: {exc}")
        return problems


def read_pack(path: str | Path) -> EventPack:
    try:
        return EventPack(path)
    except QuestFormatError as exc:
        raise PackError(f"{Path(path).name}: {exc}") from None
