"""Item, monster and map pictures (no internet needed).

They come with the editor in ``assets/`` (sprite sheets indexed by data/icons.json). They can be
rebuilt from your own extracted game by ``mhqe/artbuild.py`` (Settings > Rebuild the pictures from my
game), and without them the editor still works, with empty pictures.
"""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


class Icons:
    def __init__(self, master: tk.Misc):
        self.master = master
        self.ok = False
        self.index: dict = {}
        self._sheets: dict[str, tk.PhotoImage] = {}
        self._cache: dict[tuple, tk.PhotoImage] = {}
        try:
            with open(ROOT / "data" / "icons.json", encoding="utf-8") as f:
                self.index = json.load(f)
            self.ok = True
        except (OSError, ValueError):
            self.index = {}

    # ---------------------------------------------------------------- sheets
    def _sheet(self, name: str) -> tk.PhotoImage | None:
        if name not in self._sheets:
            try:
                self._sheets[name] = tk.PhotoImage(master=self.master, file=str(ASSETS / name))
            except (tk.TclError, OSError):
                self._sheets[name] = None
        return self._sheets[name]

    @property
    def has_art(self) -> bool:
        """True when the pictures were built from the game (monster sheet present)."""
        return (ASSETS / "monsters_27.png").is_file()

    def reload(self) -> None:
        """Re-read the index and the sheets (after the pictures were built)."""
        self._sheets.clear()
        self._cache.clear()
        try:
            with open(ROOT / "data" / "icons.json", encoding="utf-8") as f:
                self.index = json.load(f)
            self.ok = True
        except (OSError, ValueError):
            self.index = {}

    def _slice(self, sheet_name, x, y, w, h, zoom=1):
        sheet = self._sheet(sheet_name)
        if sheet is None:
            return self.blank(w * zoom)
        img = tk.PhotoImage(master=self.master, width=w * zoom, height=h * zoom)
        args = [img, "copy", sheet, "-from", x, y, x + w, y + h]
        if zoom != 1:
            args += ["-zoom", zoom, zoom]
        img.tk.call(*args)
        return img

    # ------------------------------------------------------------------ items
    def item(self, item_id: int, zoom: int = 1) -> tk.PhotoImage | None:
        key = ("item", item_id, zoom)
        if key not in self._cache:
            n = self.index.get("items", {}).get(str(item_id))
            if n is None:
                return self.blank(22 * zoom)
            c = self.index["item_cell"]
            cols = self.index["item_columns"]
            self._cache[key] = self._slice("items.png", (n % cols) * c, (n // cols) * c, c, c, zoom)
        return self._cache[key]

    # --------------------------------------------------------------- monsters
    def monster(self, em: int, size: int = 27) -> tk.PhotoImage | None:
        key = ("mon", em, size)
        if key not in self._cache:
            n = self.index.get("monsters", {}).get(str(em))
            if n is None or size not in self.index.get("monster_sizes", []):
                return self.blank(size)
            cols = self.index["monster_columns"]
            self._cache[key] = self._slice(f"monsters_{size}.png", (n % cols) * size,
                                           (n // cols) * size, size, size)
        return self._cache[key]

    def monster_note(self, em: int) -> str:
        """Why a monster shares its icon with another one (as in the game)."""
        return self.index.get("monsters_shared", {}).get(str(em), "")

    def special(self, name: str, size: int = 27) -> tk.PhotoImage | None:
        """Other icons of the game's sheet: 'delivery', 'unknown', 'danger'."""
        key = ("special", name, size)
        if key not in self._cache:
            n = self.index.get("special", {}).get(name)
            if n is None or size not in self.index.get("monster_sizes", []):
                return self.blank(size)
            cols = self.index["monster_columns"]
            self._cache[key] = self._slice(f"monsters_{size}.png", (n % cols) * size,
                                           (n // cols) * size, size, size)
        return self._cache[key]

    def quest(self, q, size: int = 27) -> tk.PhotoImage | None:
        """Icon for a quest: its first large monster, else its objective target,
        else the game's delivery-quest scroll."""
        mons = [m["Type"] for m in q.monsters if m["Type"]]
        if mons:
            return self.monster(mons[0], size)
        typ, _mode, tid, _cnt = q.objective(1)
        if typ in (0x0001, 0x0081, 0x0101, 0x8101) and str(tid) in self.index.get("monsters", {}):
            return self.monster(tid, size)
        return self.special("delivery", size)

    # ------------------------------------------------------------------- maps
    def map(self, quest_map: int, size: int = 64) -> tk.PhotoImage | None:
        key = ("map", quest_map, size)
        if key not in self._cache:
            base = self.index.get("maps", {}).get(str(quest_map))
            img = None
            if base:
                try:
                    img = tk.PhotoImage(master=self.master, file=str(ASSETS / f"{base}_{size}.png"))
                except (tk.TclError, OSError):
                    img = None
            self._cache[key] = img or self.blank(size)
        return self._cache[key]

    # ----------------------------------------------------------- map areas
    def zones(self, quest_map: int) -> dict | None:
        """{'size', 'file', 'areas': {map number: [cell, x, y]}} of the map's area pictures, or None."""
        return self.index.get("zones", {}).get(str(quest_map))

    def zone_layer(self, quest_map: int, cell: int, zoom: int = 1, sub: int = 1) -> tk.PhotoImage | None:
        """Cell 0 = the map, cell n = the yellow overlay of one area (same size, transparent around)."""
        z = self.zones(quest_map)
        if not z:
            return None
        key = ("zone", quest_map, cell, zoom, sub)
        if key not in self._cache:
            s = z["size"]
            img = self._slice(z["file"], cell * s, 0, s, s, zoom)
            if sub > 1 and img is not None:
                img = img.subsample(sub)
            self._cache[key] = img
        return self._cache[key]

    # ------------------------------------------------------------------ misc
    def app_icon(self) -> tk.PhotoImage | None:
        key = ("app",)
        if key not in self._cache:
            try:
                self._cache[key] = tk.PhotoImage(master=self.master, file=str(ASSETS / "app_icon.png"))
            except (tk.TclError, OSError):
                self._cache[key] = None
        return self._cache[key]

    def blank(self, size: int) -> tk.PhotoImage:
        key = ("blank", size)
        if key not in self._cache:
            self._cache[key] = tk.PhotoImage(master=self.master, width=size, height=size)
        return self._cache[key]

    def clear(self) -> None:
        """Forget cached images (e.g. after a theme change)."""
        self._cache.clear()
