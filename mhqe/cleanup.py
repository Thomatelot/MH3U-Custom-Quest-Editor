"""Going back: Citra without the editor's mods, the game as it was before the editor.

* The editor's files in Citra's mods folder (``load/mods/<title id>``): the base-game quest mod
  (``romfs/quest/<eu|us>/q_*.quest`` and ``quest.list``, ``romfs/arc/quest/<eu|us>/quest00.arc``), the
  supply boxes (``romfs/quest/support/suppNNN.supp`` under the spare numbers, the only ones the editor
  writes) and the Monster pack (the files its manifest lists). Other mods' files are left alone (a font,
  ``.quest_btl`` files...).
* The event quest files of the save (``quest1``..``quest4``): the editor keeps each one as it was before
  your first change in ``backups/original``; going back before the editor puts those back.

Nothing is deleted or replaced without a copy: what a clean-up removes or replaces is copied first to
``backups/cleanup/<date>/`` in the editor's folder, with a list (``cleanup.json``), so "Put back" can
undo the last clean-up. The previous version of the editor itself is kept by the updater
(``update_backups``, see updater.py).
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from . import monsterpack, supp
from .packs import PACK_NAMES

CLEAN_DIR = "cleanup"
INFO = "cleanup.json"


def editor_mod_files(title_dirs) -> list[Path]:
    """The editor's files found in these ``load/mods/<title id>`` folders."""
    out: list[Path] = []
    for d in title_dirs:
        d = Path(d)
        man = monsterpack.read_manifest(d)
        if man:
            out += [d / "romfs" / "arc" / "enemy" / f"em{em:03d}.arc" for em in man.get("monsters", [])]
            out += [d / "exefs" / "code.ips", d / monsterpack.MANIFEST]
        r = d / "romfs"
        for region in ("eu", "us"):
            q = r / "quest" / region
            if q.is_dir():
                out += sorted(p for p in q.glob("q_*.quest") if p.name[2:7].isdigit())
                out.append(q / "quest.list")
            out.append(r / "arc" / "quest" / region / "quest00.arc")
        out += [r / "quest" / "support" / supp.file_name(no) for no in supp.SPARE]
    seen, res = set(), []
    for p in out:
        if p.is_file() and p not in seen:
            seen.add(p)
            res.append(p)
    return res


def changed_event_files(pack_dir, original_dir) -> list[tuple[Path, Path]]:
    """[(event quest file of the save, its copy from before your first change)] for those that differ."""
    if not pack_dir or not original_dir:
        return []
    out = []
    for name in PACK_NAMES:
        cur, orig = Path(pack_dir) / name, Path(original_dir) / name
        try:
            if cur.is_file() and orig.is_file() and cur.read_bytes() != orig.read_bytes():
                out.append((cur, orig))
        except OSError:
            continue
    return out


def _new_folder(backup_root: Path, reason: str) -> Path:
    base = Path(backup_root) / CLEAN_DIR / time.strftime("%Y-%m-%d_%H-%M-%S")
    dest, n = base, 1
    while dest.exists():
        n += 1
        dest = Path(f"{base}_{n}")
    dest.mkdir(parents=True)
    (dest / INFO).write_text(json.dumps({"reason": reason, "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                                         "files": []}, indent=1), encoding="utf-8")
    return dest


def _keep(dest: Path, files) -> None:
    """Copy files into the clean-up folder and list them (path -> copy)."""
    info = json.loads((dest / INFO).read_text(encoding="utf-8"))
    for f in files:
        f = Path(f)
        copy = Path("files") / f"{len(info['files']):03d}_{f.name}"
        (dest / copy).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest / copy)
        info["files"].append({"path": str(f), "copy": copy.as_posix()})
    (dest / INFO).write_text(json.dumps(info, indent=1), encoding="utf-8")


def _remove_empty_dirs(path: Path, stop: Path) -> None:
    path, stop = Path(path), Path(stop)
    while path != stop and stop in path.parents:
        try:
            path.rmdir()                           # only when empty
        except OSError:
            return
        path = path.parent


def remove_mods(files, title_dirs, backup_root: Path,
                reason: str = "remove the editor's mods from Citra") -> tuple[Path, list[str]]:
    """Copy the files to backups/cleanup/<date>/, then delete them from Citra (and the folders left empty
    under the title folder). Returns (the clean-up folder, [errors]): a file Citra holds open, say."""
    files = [Path(f) for f in files]
    dest = _new_folder(backup_root, reason)
    _keep(dest, files)
    errors = []
    for f in files:
        try:
            f.unlink()
        except OSError as exc:
            errors.append(f"{f}: {exc}")
            continue
        for t in title_dirs:
            if Path(t) in f.parents:
                _remove_empty_dirs(f.parent, Path(t))
    return dest, errors


def restore_originals(pairs, dest: Path) -> tuple[int, list[str]]:
    """Put back the event quest files from before your first change (the current ones are copied to the
    clean-up folder ``dest`` first). Returns (files put back, [errors])."""
    _keep(dest, [cur for cur, _orig in pairs])
    done, errors = 0, []
    for cur, orig in pairs:
        try:
            shutil.copy2(orig, cur)
            done += 1
        except OSError as exc:
            errors.append(f"{cur}: {exc}")
    return done, errors


def back_to_before(title_dirs, pack_dir, original_dir, backup_root: Path) -> tuple[Path, int, int, list[str]]:
    """Remove the editor's mods from Citra and put back the original event quest files.
    Returns (clean-up folder, files removed, files put back, [errors])."""
    mods = editor_mod_files(title_dirs)
    pairs = changed_event_files(pack_dir, original_dir)
    dest, errors = remove_mods(mods, title_dirs, backup_root, reason="back to the game as it was before the editor")
    done, errors2 = restore_originals(pairs, dest)
    return dest, len(mods) - len(errors), done, errors + errors2


def last_cleanup(backup_root: Path) -> tuple[Path, dict] | None:
    root = Path(backup_root) / CLEAN_DIR
    if not root.is_dir():
        return None
    for d in sorted(root.iterdir(), reverse=True):
        try:
            info = json.loads((d / INFO).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if info.get("files") and not info.get("put_back"):
            return d, info
    return None


def put_back(folder: Path) -> int:
    """Copy back every file a clean-up removed or replaced (to where it was)."""
    folder = Path(folder)
    info = json.loads((folder / INFO).read_text(encoding="utf-8"))
    n = 0
    for e in info.get("files", []):
        src, dst = folder / e["copy"], Path(e["path"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    info["put_back"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (folder / INFO).write_text(json.dumps(info, indent=1), encoding="utf-8")
    return n
