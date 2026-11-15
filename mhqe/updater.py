"""Update the editor from its GitHub repository, keeping everything the user made.

Only runs when the user asks (Settings > Check for updates): the editor never goes online by itself.

* Finding the newest version: the latest GitHub release, the highest version tag and the version of
  the main branch (``mhqe/__init__.py``) are compared; the highest wins (a release or tag before the
  branch when they are equal). So it works whether or not releases and tags are published.
* What is replaced: only the files of the downloaded version. Files of the user are never written:
  settings, custom supply boxes, the library, the workspace (base-game edits, roaming lists), the
  backups and the output mods. Program files that the new version no longer has are left alone.
* Before anything is replaced: a zip of the user's files and a copy of every program file that will
  change go to ``update_backups/<date> <old> to <new>/``. If writing fails half way, the program
  files are put back at once; "Go back to version ..." does the same later.
* A copy of the editor that is a git working copy (``.git`` folder) is not updated: use git.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import ssl
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from . import __version__

REPO = "Thomatelot/MH3U-Custom-Quest-Editor"
BRANCH = "main"
API = f"https://api.github.com/repos/{REPO}"
RAW = f"https://raw.githubusercontent.com/{REPO}"
CODELOAD = f"https://codeload.github.com/{REPO}/zip"
PAGE = f"https://github.com/{REPO}"
TIMEOUT = 25
MAX_ZIP = 200 * 1024 * 1024

# the user's own files and folders (top level of the editor's folder): never written, never deleted
USER_FILES = {"settings.json", "custom_supply.json", "error_log.txt"}
USER_DIRS = {"library", "workspace", "backups", "output", "update_backups", ".venv", "venv"}
DATA_IN_ZIP = ("settings.json", "custom_supply.json", "library", "workspace")   # copied to your_data.zip
BACKUP_DIR = "update_backups"


class UpdateError(Exception):
    """Something the user should read (no connection, bad download...)."""


def parse_version(text: str) -> tuple[int, ...] | None:
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    return tuple(int(x or 0) for x in m.groups()) if m else None


def newer(a: str, b: str) -> bool:
    """True if version a is above version b."""
    va, vb = parse_version(a), parse_version(b)
    return bool(va and vb and va > vb)


# ------------------------------------------------------------------- network
def _get(url: str, accept: str = "application/vnd.github+json") -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": f"MH3U-Custom-Quest-Editor/{__version__}",
                                               "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as r:
            data = r.read(MAX_ZIP + 1)
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"GitHub answered {exc.code} for {url}") from exc
    except (urllib.error.URLError, OSError, ssl.SSLError) as exc:
        raise UpdateError(f"Could not reach GitHub ({getattr(exc, 'reason', exc)}). "
                          "Check the Internet connection and try again.") from exc
    if len(data) > MAX_ZIP:
        raise UpdateError("The download is larger than expected; stopped.")
    return data


def _json(url: str):
    try:
        return json.loads(_get(url).decode("utf-8"))
    except ValueError as exc:
        raise UpdateError(f"Unexpected answer from GitHub for {url}") from exc


def _branch_version(ref: str) -> str | None:
    text = _get(f"{RAW}/{ref}/mhqe/__init__.py", "text/plain").decode("utf-8", "replace")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else None


def find_latest() -> dict:
    """{'version', 'ref', 'kind' ('release', 'tag' or 'branch'), 'notes'} of the newest version."""
    found = []
    try:
        rel = _json(f"{API}/releases/latest")
        if parse_version(rel.get("tag_name", "")):
            found.append({"version": ".".join(map(str, parse_version(rel["tag_name"]))), "ref": rel["tag_name"],
                          "kind": "release", "notes": rel.get("body") or "", "rank": 2})
    except UpdateError:
        pass                                   # no release published (GitHub answers 404)
    try:
        tags = [t["name"] for t in _json(f"{API}/tags?per_page=100") if parse_version(t.get("name", ""))]
        if tags:
            best = max(tags, key=parse_version)
            found.append({"version": ".".join(map(str, parse_version(best))), "ref": best, "kind": "tag",
                          "notes": "", "rank": 1})
    except UpdateError:
        pass
    errors = []
    try:
        v = _branch_version(BRANCH)
        if v:
            found.append({"version": v, "ref": BRANCH, "kind": "branch", "notes": "", "rank": 0})
    except UpdateError as exc:
        errors.append(str(exc))
    if not found:
        raise UpdateError(errors[0] if errors else "No version of the editor was found on GitHub.")
    best = max(found, key=lambda f: (parse_version(f["version"]), f["rank"]))
    best.pop("rank")
    if not best["notes"]:
        try:
            best["notes"] = changes_since(_get(f"{RAW}/{best['ref']}/CHANGELOG.md", "text/plain")
                                          .decode("utf-8", "replace"), __version__)
        except UpdateError:
            best["notes"] = ""
    return best


def changes_since(changelog: str, current: str) -> str:
    """The CHANGELOG sections of the versions above ``current``."""
    out, keep = [], False
    for line in changelog.splitlines():
        if line.startswith("## "):
            keep = newer(line[3:], current)
        if keep:
            out.append(line)
    return "\n".join(out).strip()


def download(ref: str) -> bytes:
    return _get(f"{CODELOAD}/{ref}", "application/zip")


# ------------------------------------------------------------------ the zip
def read_zip(data: bytes, expect_version: str | None = None) -> dict[str, bytes]:
    """{relative path: content} of the program files in a downloaded zip, checked."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise UpdateError("The download is not a valid zip file.") from exc
    names = [n for n in z.namelist() if not n.endswith("/")]
    tops = {n.split("/", 1)[0] for n in z.namelist()}
    if len(tops) != 1:
        raise UpdateError("The download does not have the expected layout.")
    top = tops.pop() + "/"
    files: dict[str, bytes] = {}
    for n in names:
        rel = n[len(top):]
        parts = rel.split("/")
        if not rel or rel.startswith("/") or ".." in parts or ":" in rel or "\\" in rel:
            raise UpdateError(f"Unsafe path in the download: {n}")
        if is_user_path(rel):
            continue                           # never shipped, but never written either
        files[rel] = z.read(n)
    for need in ("mh3u_quest_editor.py", "mhqe/__init__.py", "mhqe/app.py"):
        if need not in files:
            raise UpdateError(f"The download is not the editor ({need} is missing).")
    m = re.search(rb'__version__\s*=\s*"([^"]+)"', files["mhqe/__init__.py"])
    got = m.group(1).decode() if m else "?"
    if expect_version and got != expect_version:
        raise UpdateError(f"The download is version {got}, not {expect_version}.")
    return files


def is_user_path(rel: str) -> bool:
    first = rel.replace("\\", "/").split("/", 1)[0]
    return first in USER_DIRS or (first in USER_FILES and "/" not in rel) or "/__pycache__/" in f"/{rel}" \
        or rel.endswith(".pyc")


# ------------------------------------------------------------------- apply
def can_update(app_dir: Path) -> str | None:
    """Why this copy can not be updated by the editor, or None."""
    if (Path(app_dir) / ".git").exists():
        return "This copy of the editor is a git working copy: update it with git (or GitHub Desktop)."
    if not (Path(app_dir) / "mhqe" / "__init__.py").is_file():
        return "The editor's folder was not found."
    return None


def plan(app_dir: Path, files: dict[str, bytes]) -> dict:
    """What an update would do: {'changed': [...], 'added': [...], 'same': n}."""
    changed, added, same = [], [], 0
    for rel, data in sorted(files.items()):
        p = Path(app_dir) / rel
        if not p.exists():
            added.append(rel)
        elif p.is_file() and p.read_bytes() == data:
            same += 1
        else:
            changed.append(rel)
    return {"changed": changed, "added": added, "same": same}


def _zip_user_data(app_dir: Path, target: Path) -> int:
    n = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for name in DATA_IN_ZIP:
            p = app_dir / name
            if p.is_file():
                z.write(p, name)
                n += 1
            elif p.is_dir():
                for f in sorted(p.rglob("*")):
                    if f.is_file():
                        z.write(f, f.relative_to(app_dir).as_posix())
                        n += 1
    return n


def apply(app_dir: Path, files: dict[str, bytes], new_version: str, progress=None) -> Path:
    """Install ``files`` (from read_zip) into ``app_dir``. Returns the backup folder."""
    app_dir = Path(app_dir)
    why = can_update(app_dir)
    if why:
        raise UpdateError(why)
    work = plan(app_dir, files)
    stamp = time.strftime("%Y-%m-%d %H-%M-%S")
    bdir = app_dir / BACKUP_DIR / f"{stamp} {__version__} to {new_version}"
    (bdir / "program").mkdir(parents=True, exist_ok=False)
    say = progress or (lambda _t: None)
    say("Saving a copy of your quests, boxes and settings...")
    _zip_user_data(app_dir, bdir / "your_data.zip")
    say("Saving a copy of the program files...")
    for rel in work["changed"]:
        dst = bdir / "program" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(app_dir / rel, dst)
    info = {"from": __version__, "to": new_version, "date": stamp, "changed": work["changed"],
            "added": work["added"]}
    (bdir / "update.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    say("Writing the new version...")
    done: list[str] = []
    try:
        for rel in work["changed"] + work["added"]:
            p = app_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + ".update_tmp")
            tmp.write_bytes(files[rel])
            tmp.replace(p)
            done.append(rel)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        _put_back(app_dir, bdir, info, only=set(done))
        raise UpdateError(f"The update could not write {p} ({exc}). The previous version was put back.") from exc
    _clear_caches(app_dir)
    return bdir


def _put_back(app_dir: Path, bdir: Path, info: dict, only: set | None = None) -> None:
    for rel in info["changed"]:
        if only is None or rel in only:
            src = bdir / "program" / rel
            if src.is_file():
                (app_dir / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, app_dir / rel)
    for rel in info["added"]:
        if only is None or rel in only:
            (app_dir / rel).unlink(missing_ok=True)
    _clear_caches(app_dir)


def _clear_caches(app_dir: Path) -> None:
    for d in list(app_dir.rglob("__pycache__")):
        if d.relative_to(app_dir).parts[0] not in USER_DIRS:
            shutil.rmtree(d, ignore_errors=True)


def last_update(app_dir: Path) -> tuple[Path, dict] | None:
    """(folder, info) of the most recent update that can be undone, or None."""
    root = Path(app_dir) / BACKUP_DIR
    if not root.is_dir():
        return None
    for d in sorted(root.iterdir(), reverse=True):
        f = d / "update.json"
        if f.is_file():
            try:
                info = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if not info.get("undone"):
                return d, info
    return None


def undo(app_dir: Path, bdir: Path) -> dict:
    """Put back the program files of the version before this update (your files are not touched)."""
    info = json.loads((bdir / "update.json").read_text(encoding="utf-8"))
    _put_back(Path(app_dir), bdir, info)
    info["undone"] = time.strftime("%Y-%m-%d %H-%M-%S")
    (bdir / "update.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    return info
