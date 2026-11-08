"""Quest library: your own quests saved as files, outside the game.

Each quest is one ``.mh3uq`` file (the raw quest record, the same format as
the game's q_NNNNN.quest files, which can also be imported).
"""
from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from .project import Entry, write_atomic
from .quest import Quest, QuestFormatError

EXT = ".mh3uq"


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")[:40] or "quest"


class LibrarySource:
    kind = "library"
    title = "Quest library"
    can_create = True

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.quests: dict[str, Quest] = {}
        self.unsaved: set[str] = set()
        self.reload()

    def reload(self) -> None:
        self.quests, self.unsaved = {}, set()
        for f in sorted(self.folder.glob(f"*{EXT}")):
            try:
                self.quests[f.name] = Quest(f.read_bytes())
            except (OSError, QuestFormatError):
                continue

    def entries(self) -> list[Entry]:
        out = []
        for key, q in sorted(self.quests.items(), key=lambda kv: kv[1].get_text("name", 0).lower()):
            out.append(Entry(key, "My quests", q, key[:-len(EXT)], key in self.unsaved))
        return out

    def get(self, key):
        return self.quests.get(key)

    def group_summary(self, name):
        return f"{name}  ({len(self.quests)})"

    def mark_dirty(self, key):
        self.unsaved.add(key)

    def numbers_except(self, key=None):
        return set()

    def fit_problem(self, key):
        return None

    def dirty(self):
        return bool(self.unsaved)

    def save(self):
        written = []
        for key in sorted(self.unsaved):
            if key in self.quests:
                p = self.folder / key
                write_atomic(p, self.quests[key].to_bytes())
                written.append(p)
        self.unsaved = set()
        return written

    # ---------------------------------------------------------- actions
    def add(self, quest: Quest, name_hint: str | None = None) -> str:
        base = f"{quest.get('quest_no'):05d}_{_slug(name_hint or quest.get_text('name', 0))}"
        key = base + EXT
        n = 1
        while (self.folder / key).exists() or key in self.quests:
            n += 1
            key = f"{base}_{n}{EXT}"
        q = quest.copy()
        write_atomic(self.folder / key, q.to_bytes())
        self.quests[key] = q
        return key

    def import_file(self, path: Path) -> str:
        data = Path(path).read_bytes()
        q = Quest(data)                       # raises QuestFormatError
        return self.add(q)

    def export(self, key: str, path: Path) -> None:
        write_atomic(Path(path), self.quests[key].to_bytes().rstrip(b"\0"))

    def delete(self, key: str) -> Path:
        trash = self.folder / "_deleted"
        trash.mkdir(exist_ok=True)
        dest = trash / f"{time.strftime('%Y%m%d-%H%M%S')}_{key}"
        if (self.folder / key).exists():
            shutil.move(str(self.folder / key), dest)
        self.quests.pop(key, None)
        self.unsaved.discard(key)
        return dest
