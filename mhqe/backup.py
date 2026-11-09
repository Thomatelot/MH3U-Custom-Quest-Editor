"""Backups made before every save.

backups/
  original/<pack>                    first version of each pack ever seen (never replaced)
  full/<YYYY-MM-DD_HH-MM-SS>/        all quest1..quest4 as they were just before a save
        quest1 .. quest4, info.json
  quests/<stamp>__<pack>-slot<NN>__q<no>.mh3uq   one file per quest that a save replaced,
        edited or deleted (+ .json with its name), so a single quest can be brought back.

Rolling clean-up (to save space): the most recent full backups are kept (KEEP_FULL by
default) and, for every quest, its most recent backups (KEEP_PER_QUEST). Failsafe, whatever the
settings: the original files (backups/original), the very first full backup ever made, the first
backup of every quest (the version before your first change) and old-format backups are never
deleted, and nothing outside backups/full and backups/quests is ever touched.
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

KEEP_FULL = 20
KEEP_PER_QUEST = 5
_NEW = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})")
_LEGACY = re.compile(r"^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})$")


def _stamp() -> str:
    return time.strftime("%Y-%m-%d_%H-%M-%S")


def _safe(text: str, n: int = 40) -> str:
    return re.sub(r"[^A-Za-z0-9 _.'-]+", "", text).strip()[:n] or "quest"


class BackupManager:
    def __init__(self, root: Path, keep_full: int = KEEP_FULL, keep_per_quest: int = KEEP_PER_QUEST):
        self.root = Path(root)
        self.keep_full = keep_full
        self.keep_per_quest = keep_per_quest

    # ----------------------------------------------------------- folders
    @property
    def full_dir(self) -> Path:
        return self.root / "full"

    @property
    def quest_dir(self) -> Path:
        return self.root / "quests"

    @property
    def original_dir(self) -> Path:
        return self.root / "original"

    # ------------------------------------------------------------ writing
    def keep_original(self, path: Path) -> None:
        orig = self.original_dir / path.name
        if path.exists() and not orig.exists():
            orig.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, orig)

    def snapshot(self, files, reason: str = "before save") -> Path | None:
        files = [Path(f) for f in files if Path(f).exists()]
        if not files:
            return None
        base = self.full_dir / _stamp()
        dest = base
        n = 1
        while dest.exists():
            n += 1
            dest = Path(f"{base}_{n}")
        first = not any(s.get("kind") == "full" for s in self.list_full())
        dest.mkdir(parents=True)
        for f in files:
            self.keep_original(f)
            shutil.copy2(f, dest / f.name)
        (dest / "info.json").write_text(json.dumps(
            {"reason": reason, "time": time.strftime("%Y-%m-%d %H:%M:%S"),
             "source": str(files[0].parent), "files": [f.name for f in files],
             "protected": first}, indent=1),
            encoding="utf-8")
        self.prune()
        return dest

    def save_quest(self, record: bytes, *, pack: str, slot: int, quest_no: int, name: str,
                   reason: str) -> Path:
        self.quest_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{_stamp()}__{pack}-slot{slot + 1:02d}__q{quest_no:05d}"
        path = self.quest_dir / f"{stem}.mh3uq"
        n = 1
        while path.exists():
            n += 1
            path = self.quest_dir / f"{stem}_{n}.mh3uq"
        first = not any(b.get("quest_no") == quest_no for b in self.list_quests())
        path.write_bytes(record.rstrip(b"\0") or record)
        path.with_suffix(".json").write_text(json.dumps(
            {"name": name, "pack": pack, "slot": slot + 1, "quest_no": quest_no, "reason": reason,
             "time": time.strftime("%Y-%m-%d %H:%M:%S"), "protected": first}, indent=1), encoding="utf-8")
        self.prune_quests()
        return path

    # ----------------------------------------------------------- clean-up
    def _deletable(self, path: Path, inside: Path) -> bool:
        """Failsafe used by every deletion: only a plain file or folder directly inside backups/full
        or backups/quests, never the original files, never a link, never anything else."""
        try:
            path, inside = Path(path), Path(inside)
            if path.is_symlink() or path.parent.resolve() != inside.resolve():
                return False
            if inside.resolve() not in (self.full_dir.resolve(), self.quest_dir.resolve()):
                return False
            orig = self.original_dir.resolve()
            return orig not in path.resolve().parents and path.resolve() != orig
        except OSError:
            return False

    def protected_full(self) -> Path | None:
        """The first full backup ever made (marked when it was made; for older setups: the oldest)."""
        snaps = [s for s in self.list_full() if s.get("kind") == "full"]
        marked = [s for s in snaps if s.get("protected")]
        if marked:
            return marked[-1]["path"]
        return snaps[-1]["path"] if snaps else None

    def prune(self, keep: int | None = None) -> int:
        """Delete the oldest full backups beyond *keep*, except the protected first one."""
        keep = max(3, self.keep_full if keep is None else keep)
        snaps = [s for s in self.list_full() if s.get("kind") == "full"]
        first = self.protected_full()
        n = 0
        for s in snaps[keep:]:
            if s["path"] == first or s.get("protected") or not self._deletable(s["path"], self.full_dir):
                continue
            shutil.rmtree(s["path"], ignore_errors=True)
            n += 1
        return n

    def prune_quests(self, keep: int | None = None) -> int:
        """For every quest number, delete its oldest backups beyond *keep*; its first backup (the
        version before the first change) is always kept."""
        keep = max(2, self.keep_per_quest if keep is None else keep)
        by_no: dict = {}
        for b in self.list_quests():                      # newest first
            by_no.setdefault((b.get("quest_no"), b.get("pack"), b.get("slot")), []).append(b)
        n = 0
        for items in by_no.values():
            first = items[-1]["path"]                     # the oldest one = before the first change
            for b in items[keep:]:
                p = b["path"]
                if p == first or b.get("protected") or not self._deletable(p, self.quest_dir):
                    continue
                for f in (p, p.with_suffix(".json")):
                    if f.exists() and self._deletable(f, self.quest_dir):
                        f.unlink()
                n += 1
        return n

    def size(self) -> int:
        """Bytes used by all backups."""
        total = 0
        for f in self.root.rglob("*") if self.root.is_dir() else []:
            if f.is_file():
                total += f.stat().st_size
        return total

    # ------------------------------------------------------------ reading
    def list_full(self) -> list[dict]:
        """Full backups, newest first; the 'original files' entry comes last."""
        out = []
        if self.full_dir.is_dir():
            for d in self.full_dir.iterdir():
                if not d.is_dir():
                    continue
                info = {}
                try:
                    info = json.loads((d / "info.json").read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    pass
                m = _NEW.match(d.name)
                key = info.get("time") or (f"{m[1]} {m[2]}:{m[3]}:{m[4]}" if m else d.name)
                out.append({"path": d, "time": key, "reason": info.get("reason", ""), "kind": "full",
                            "protected": bool(info.get("protected")),
                            "key": key + d.name[19:],
                            "files": sorted(p.name for p in d.iterdir() if p.name != "info.json")})
        if self.root.is_dir():                      # flat backup folders (backups/YYYYMMDD-HHMMSS)
            for d in self.root.iterdir():
                m = _LEGACY.match(d.name)
                if m and d.is_dir():
                    t = f"{m[1]}-{m[2]}-{m[3]} {m[4]}:{m[5]}:{m[6]}"
                    out.append({"path": d, "time": t, "reason": "before save", "kind": "legacy",
                                "key": t, "files": sorted(p.name for p in d.iterdir())})
        out.sort(key=lambda s: s["key"], reverse=True)
        orig = self.original_dir
        if orig.is_dir() and any(orig.iterdir()):
            out.append({"path": orig, "time": "first version", "reason": "original files (never deleted)",
                        "kind": "original", "key": "", "files": sorted(p.name for p in orig.iterdir())})
        return out

    def list_quests(self) -> list[dict]:
        out = []
        if self.quest_dir.is_dir():
            for f in sorted(self.quest_dir.glob("*.mh3uq"), reverse=True):
                meta = {}
                try:
                    meta = json.loads(f.with_suffix(".json").read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    pass
                out.append({"path": f, **meta})
        return out

    def restore_full(self, snapshot: Path, dest_folder: Path, names=None) -> list[Path]:
        """Copy a snapshot's pack files back (the current files are backed up first)."""
        snapshot, dest_folder = Path(snapshot), Path(dest_folder)
        files = [p for p in snapshot.iterdir() if p.name != "info.json" and (names is None or p.name in names)]
        self.snapshot([dest_folder / p.name for p in files], reason="before restoring a backup")
        written = []
        for p in files:
            shutil.copy2(p, dest_folder / p.name)
            written.append(dest_folder / p.name)
        return written
