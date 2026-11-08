"""Quest sources (event packs / ROM quests), backups, settings, emulator lookup.

Nothing here touches your original game files unless you press Save: packs
are written in place (after a backup), the ROM is never modified - a mod
folder is generated instead.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from . import arc as arcmod
from . import gamedata as G
from .backup import BackupManager
from .packs import (DATA, PACK_NAMES, EventPack, PackError, fit_record,
                    file_name_for)
from .quest import Quest, QuestFormatError

APP_DIR = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------ settings
class Settings:
    """Small JSON settings file stored next to the program (or in the home
    folder when the program folder is read-only)."""

    def __init__(self):
        self.path = APP_DIR / "settings.json"
        self.data: dict = {}
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        self.data[key] = value
        self.save()

    def save(self) -> None:
        for path in (self.path, Path.home() / ".mh3u_quest_editor_settings.json"):
            try:
                path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
                self.path = path
                return
            except OSError:
                continue


# ------------------------------------------------------------------- backups
class Backups(BackupManager):
    """backups/ next to the program for the EU version (as in 1.0), backups/us/ for the US one,
    so the save files of the two versions are never mixed."""

    def __init__(self, root: Path | None = None):
        if root is None:
            root = APP_DIR / "backups" if G.REGION == "eu" else APP_DIR / "backups" / G.REGION
        super().__init__(Path(root))


def write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


# ----------------------------------------------------------- emulator lookup
def _emulator_roots() -> list[Path]:
    roots: list[Path] = []
    appdata = os.environ.get("APPDATA")
    home = Path.home()
    if appdata:
        for name in ("Citra", "Azahar", "Lime3DS", "Mandarine", "PabloMK7-Citra"):
            roots.append(Path(appdata) / name)
    for rel in (".local/share/citra-emu", ".local/share/azahar-emu",
                ".local/share/lime3ds-emu", "Library/Application Support/Citra",
                "Library/Application Support/Azahar"):
        roots.append(home / rel)
    return roots


def find_pack_dir(start: str | Path, max_depth: int = 10, extdata: str | None = None) -> Path | None:
    """Return the ``.../extdata/00000000/<extdata id>/user`` folder of the selected game version
    (00000B1D for EU, 00000AE4 for US) found at or below *start* (also accepts the folder that
    directly holds quest1..4)."""
    want = (extdata or G.EXTDATA_ID).upper()
    start = Path(start)
    if not start.is_dir():
        return None
    if any((start / n).is_file() for n in PACK_NAMES):
        return start
    stack = [(start, 0)]
    while stack:
        p, depth = stack.pop()
        if depth > max_depth:
            continue
        try:
            subs = sorted(c for c in p.iterdir() if c.is_dir())
        except OSError:
            continue
        for c in subs:
            if (p.name == "00000000" and c.name.upper() == want
                    and (c / "user").is_dir()):
                return c / "user"
            stack.append((c, depth + 1))
    return None


def find_emulator_pack_dirs(region: str | None = None) -> list[Path]:
    ext = G.REGIONS[region]["extdata"] if region else None
    found = []
    for root in _emulator_roots():
        sdmc = root / "sdmc"
        if sdmc.is_dir():
            hit = find_pack_dir(sdmc, extdata=ext)
            if hit and hit not in found:
                found.append(hit)
    return found


def regions_with_saves() -> list[str]:
    """Game versions that have a save in an emulator folder of this computer."""
    return [r for r in G.REGIONS if find_emulator_pack_dirs(r)]


def pack_dir_region(folder: str | Path | None) -> str | None:
    """'eu' or 'us' when the folder is inside the extdata of one version, else None."""
    if not folder:
        return None
    parts = [x.upper() for x in Path(folder).parts]
    for r, info in G.REGIONS.items():
        if info["extdata"] in parts:
            return r
    return None


def find_emulator_title_dirs() -> list[Path]:
    """Citra-style ``load/mods/<title id>`` folders of the selected version (where romfs/ and
    exefs/ mods go), for every emulator whose ``load`` folder exists."""
    return [root / "load" / "mods" / G.TITLE_ID for root in _emulator_roots() if (root / "load").is_dir()]


def find_emulator_mod_dirs() -> list[Path]:
    """Citra-style ``load/mods/<title id>/romfs`` folders (created if the
    emulator's ``load`` folder exists)."""
    out = []
    for root in _emulator_roots():
        if (root / "load").is_dir():
            out.append(root / "load" / "mods" / G.TITLE_ID / "romfs")
    return out


# --------------------------------------------------------------------- entries
class Entry:
    """One row in the quest list."""

    def __init__(self, key: str, group: str, quest: Quest | None, slot: str,
                 modified: bool = False):
        self.key = key
        self.group = group
        self.quest = quest
        self.slot = slot
        self.modified = modified

    @property
    def free(self) -> bool:
        return self.quest is None


# ----------------------------------------------------------------- pack source
class PackSource:
    kind = "packs"
    title = "Event quests (game extdata)"
    can_create = True

    def __init__(self, folder: str | Path, backups: Backups, reserved=()):
        self.folder = Path(folder)
        self.backups = backups
        self.reserved = set(reserved)          # base-game numbers (cannot be reused)
        self.packs: dict[str, EventPack] = {}
        self.reload()

    def reload(self) -> None:
        self.packs = {}
        for name in PACK_NAMES:
            p = self.folder / name
            if p.is_file():
                self.packs[name] = EventPack(p)
        if not self.packs:
            raise PackError(f"No quest1..quest4 files found in {self.folder}")

    # -------------------------------------------------------------- listing
    def entries(self) -> list[Entry]:
        out = []
        for name, pack in self.packs.items():
            for s in pack.slots:
                out.append(Entry(f"{name}:{s.index}", name, s.quest,
                                 f"{s.index + 1:02d}", s.dirty))
        return out

    def _split(self, key: str):
        name, idx = key.split(":")
        return self.packs[name], int(idx)

    def get(self, key: str) -> Quest | None:
        pack, idx = self._split(key)
        return pack.slots[idx].quest

    def group_summary(self, name: str) -> str:
        p = self.packs[name]
        return f"{name}  ({len(p.used_slots())}/{len(p.slots)} used)"

    # -------------------------------------------------------------- editing
    def mark_dirty(self, key: str) -> None:
        pack, idx = self._split(key)
        pack.mark_dirty(idx)

    def numbers_except(self, key: str | None = None) -> set[int]:
        nums = set(self.reserved)
        for name, pack in self.packs.items():
            for s in pack.slots:
                if s.quest is not None and f"{name}:{s.index}" != key:
                    nums.add(s.quest.get("quest_no"))
        return nums

    def next_free_number(self, base: int = 20325) -> int:
        taken = self.numbers_except()
        n = base
        while n in taken:
            n += 1
        return n

    def create(self, key: str, template: Quest, quest_no: int) -> Quest:
        if quest_no in self.numbers_except():
            raise PackError(f"Quest number {quest_no} is already used.")
        pack, idx = self._split(key)
        return pack.create_quest(idx, template, quest_no)

    def delete(self, key: str) -> None:
        pack, idx = self._split(key)
        pack.clear_slot(idx)

    def place(self, key: str, quest: Quest, quest_no: int | None = None) -> Quest:
        """Put a copy of *quest* into a slot (free or not), optionally renumbered."""
        pack, idx = self._split(key)
        s = pack.slots[idx]
        q = quest.copy()
        q.pad_to(DATA)
        if quest_no is not None:
            q.set("quest_no", quest_no)
        if q.get("quest_no") in self.numbers_except(key):
            raise PackError(f"Quest number {q.get('quest_no')} is already used by another quest.")
        fit_record(q.to_bytes(), DATA)
        s.quest = q
        s.filename = file_name_for(q.get("quest_no"))
        s.dirty = True
        return q

    def renumber(self, key: str, quest_no: int) -> None:
        if quest_no in self.numbers_except(key):
            raise PackError(f"Quest number {quest_no} is already used.")
        pack, idx = self._split(key)
        pack.set_quest_no(idx, quest_no)

    def fit_problem(self, key: str) -> str | None:
        q = self.get(key)
        if q is None:
            return None
        try:
            fit_record(q.to_bytes(), DATA)
        except PackError as exc:
            return str(exc)
        return None

    # ----------------------------------------------------------------- save
    def dirty(self) -> bool:
        return any(p.dirty for p in self.packs.values())

    def save(self) -> list[Path]:
        problems = []
        for pack in self.packs.values():
            if pack.dirty:
                problems += pack.validate_fit()
        if problems:
            raise PackError("Cannot save:\n" + "\n".join(problems))
        dirty = [n for n, p in self.packs.items() if p.dirty]
        if not dirty:
            return []
        # 1) full backup of every pack file, 2) one file per quest being replaced
        self.backups.snapshot([self.folder / n for n in self.packs], reason="before save")
        for name in dirty:
            pack = self.packs[name]
            for s in pack.slots:
                if not s.dirty or s.raw[:4] != b"QTDS":
                    continue
                old = Quest(s.raw[:DATA])
                if s.quest is not None and s.serialize() == s.raw:
                    continue
                reason = "deleted" if s.quest is None else "replaced or edited"
                self.backups.save_quest(s.raw[:DATA], pack=name, slot=s.index,
                                        quest_no=old.get("quest_no"), name=old.get_text("name", 0),
                                        reason=reason)
        written = []
        for name in dirty:
            path = self.folder / name
            write_atomic(path, self.packs[name].to_bytes())
            written.append(path)
        self.reload()
        return written

    def restore_quest(self, key: str, record: bytes) -> Quest:
        """Put a backed-up quest record into a slot (keeps its own number if free)."""
        q = Quest(record)
        no = q.get("quest_no")
        if no in self.numbers_except(key):
            no = self.next_free_number()
        return self.place(key, q, no)


# ------------------------------------------------------------------ ROM source
class RomSource:
    """Base-game quests read from quest00.arc (or the loose files) of an
    extracted ROM. Edits are kept in ``workspace/rom_edits`` and exported as a
    mod folder (``romfs/quest/<eu|us>/*.quest`` + ``romfs/arc/quest/<eu|us>/quest00.arc``; the
    folder name is the one of the extracted game).
    """

    kind = "rom"
    title = "Base-game quests (ROM mod)"
    can_create = False

    def __init__(self, romfs: str | Path, workspace: Path | None = None,
                 load_edits: bool = True):
        self.load_edits = load_edits
        self.romfs = Path(romfs)
        self.workspace = Path(workspace) if workspace else APP_DIR / "workspace" / "rom_edits"
        self.region_dir = "us" if (self.romfs / "arc" / "quest" / "us").is_dir() or \
            (self.romfs / "quest" / "us").is_dir() else "eu"
        self.arc_path = self.romfs / "arc" / "quest" / self.region_dir / "quest00.arc"
        self.loose_dir = self.romfs / "quest" / self.region_dir
        self.quests: dict[int, Quest] = {}
        self.originals: dict[int, bytes] = {}
        self.modified: set[int] = set()       # differs from the original game file
        self.unsaved: set[int] = set()        # changed since the last Save
        self._arc: arcmod.Arc | None = None
        self.reload()

    def reload(self) -> None:
        self.quests, self.originals, self.modified = {}, {}, set()
        self.unsaved = set()
        if self.arc_path.is_file():
            self._arc = arcmod.read(self.arc_path)
            for e in self._arc.entries:
                if e.leaf.startswith("q_"):
                    self.originals[int(e.leaf[2:])] = e.data
        elif self.loose_dir.is_dir():
            self._arc = None
            for f in sorted(self.loose_dir.glob("q_*.quest")):
                self.originals[int(f.name[2:7])] = f.read_bytes()
        else:
            raise PackError(f"Could not find quest00.arc or romfs/quest/{self.region_dir} in {self.romfs}")
        for no, data in self.originals.items():
            edit = self.workspace / file_name_for(no)
            if self.load_edits and edit.is_file():
                data = edit.read_bytes()
                self.modified.add(no)
            try:
                self.quests[no] = Quest(data)
            except QuestFormatError:
                continue

    def entries(self) -> list[Entry]:
        out = []
        for no in sorted(self.quests):
            q = self.quests[no]
            out.append(Entry(str(no), self._group(no), q, f"{no:05d}", no in self.modified))
        return out

    @staticmethod
    def _group(no: int) -> str:
        if no < 1000:
            return "Tutorial / Moga"
        if no >= 60000:
            return "Grudge Match"
        return f"{no // 1000 * 1000:05d} series"

    def get(self, key: str) -> Quest | None:
        return self.quests.get(int(key))

    def group_summary(self, name: str) -> str:
        n = sum(1 for e in self.entries() if e.group == name)
        return f"{name}  ({n})"

    def mark_dirty(self, key: str) -> None:
        self.modified.add(int(key))
        self.unsaved.add(int(key))

    def numbers_except(self, key: str | None = None) -> set[int]:
        return set()

    def revert(self, key: str) -> None:
        no = int(key)
        (self.workspace / file_name_for(no)).unlink(missing_ok=True)
        self.quests[no] = Quest(self.originals[no])
        self.modified.discard(no)
        self.unsaved.discard(no)

    def fit_problem(self, key: str) -> str | None:
        return None

    def dirty(self) -> bool:
        return bool(self.unsaved)

    def save(self) -> list[Path]:
        """Store the edits in the workspace (nothing is exported yet)."""
        self.workspace.mkdir(parents=True, exist_ok=True)
        written = []
        for no in sorted(self.modified):
            p = self.workspace / file_name_for(no)
            write_atomic(p, self.quests[no].to_bytes())
            written.append(p)
        self.unsaved = set()
        return written

    def export_mod(self, out_dir: str | Path) -> list[Path]:
        """Write the mod folder: <out>/quest/<eu|us>/*.quest and
        <out>/arc/quest/<eu|us>/quest00.arc (both overridable by the emulator /
        Luma, so it works whichever copy the game reads)."""
        out = Path(out_dir)
        written = []
        for other in ("eu", "us"):                 # a mod built earlier for the other version
            if other != self.region_dir:
                for d in (out / "quest" / other, out / "arc" / "quest" / other):
                    if d.is_dir():
                        shutil.rmtree(d)
        loose = out / "quest" / self.region_dir
        loose.mkdir(parents=True, exist_ok=True)
        for no in sorted(self.modified):
            p = loose / file_name_for(no)
            write_atomic(p, self.quests[no].to_bytes())
            written.append(p)
        if self._arc is not None:
            arc = arcmod.Arc(self._arc.version,
                             [arcmod.ArcEntry(e.path, e.type_hash, e.flags, e.data)
                              for e in self._arc.entries])
            for e in arc.entries:
                if e.leaf.startswith("q_"):
                    no = int(e.leaf[2:])
                    if no in self.modified:
                        e.data = self.quests[no].to_bytes()
            target = out / "arc" / "quest" / self.region_dir / "quest00.arc"
            target.parent.mkdir(parents=True, exist_ok=True)
            write_atomic(target, arcmod.build(arc))
            written.append(target)
        return written


def read_base_numbers(romfs: str | Path | None) -> set[int]:
    """Quest numbers of the base game (so new event quests never reuse them)."""
    if not romfs:
        return set()
    try:
        return set(RomSource(romfs, load_edits=False).originals)
    except (PackError, OSError, ValueError, arcmod.ArcError):
        return set()
