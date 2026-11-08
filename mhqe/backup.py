"""Backups made before every save.

backups/
  original/<pack>                    first version of each pack ever seen (never replaced)
  full/<YYYY-MM-DD_HH-MM-SS>/        all quest1..quest4 as they were just before a save
        quest1 .. quest4, info.json
  quests/<stamp>__<pack>-slot<NN>__q<no>.mh3uq   one file per quest that a save replaced,
        edited or deleted (+ .json with its name), so a single quest can be brought back.

Old snapshots are pruned (the 40 most recent full backups are kept); originals
and per-quest backups are never pruned automatically.
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

KEEP_FULL = 40
_NEW = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})")
_LEGACY = re.compile(r"^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})$")


def _stamp() -> str:
    return time.strftime("%Y-%m-%d_%H-%M-%S")


def _safe(text: str, n: int = 40) -> str:
    return re.sub(r"[^A-Za-z0-9 _.'-]+", "", text).strip()[:n] or "quest"


class BackupManager:
    def __init__(self, root: Path):
        self.root = Path(root)

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
        dest.mkdir(parents=True)
        for f in files:
            self.keep_original(f)
            shutil.copy2(f, dest / f.name)
        (dest / "info.json").write_text(json.dumps(
            {"reason": reason, "time": time.strftime("%Y-%m-%d %H:%M:%S"),
             "source": str(files[0].parent), "files": [f.name for f in files]}, indent=1),
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
        path.write_bytes(record.rstrip(b"\0") or record)
        path.with_suffix(".json").write_text(json.dumps(
            {"name": name, "pack": pack, "slot": slot + 1, "quest_no": quest_no, "reason": reason,
             "time": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1), encoding="utf-8")
        return path

    def prune(self, keep: int = KEEP_FULL) -> None:
        """Keep the most recent full backups (originals and version-1 backups are never pruned)."""
        snaps = [s for s in self.list_full() if s.get("kind") == "full"]
        for s in snaps[keep:]:
            shutil.rmtree(s["path"], ignore_errors=True)

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
