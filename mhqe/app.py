"""Main window of the MH3U Quest Editor.

Layout follows the MH4U Custom Quest Editor:
  In-game quests  - the quests of your save (Event / Challenge tabs) and Backups
  Quest library   - your own quests kept on the PC, put into the game when you want
  Base game       - the game's own quests (written as a mod, optional)
  Guide           - how it works and what the numbers mean
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import threading
import sys
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import __version__
from . import autofill, guide, spawns, supp
from . import gamedata as G
from . import monsterpack
from . import helptext as H
from . import i18n, picker, theme
from .editor import EditorPage, stars
from .finder import Finder
from .icons import ASSETS, Icons
from .library import LibrarySource
from .packs import PackError
from .project import (APP_DIR, Backups, PackSource, RomSource, Settings, find_emulator_mod_dirs,
                      find_emulator_title_dirs, pack_dir_region, regions_with_saves,
                      find_emulator_pack_dirs, find_pack_dir, read_base_numbers)
from .quest import Quest, QuestFormatError
from .supp import CustomBoxes
from .validate import validate_quest
from .widgets import (ScrollFrame, SearchBox, StatusDot, Tooltip, center_on, disable_wheel_value_changes,
                      TribalBand, enable_tree_copy, info, install_selectable_labels, make_modal)

APP_TITLE = "MH3U Quest Editor"
ROOT_DIR = Path(__file__).resolve().parent.parent
ROM_OUTPUT = APP_DIR / "output" / "MH3U_Quest_Mod" / "romfs"
PACK_OUTPUT = APP_DIR / "output"                     # + MH3U_Monster_Pack_<EU|US>
SUPPLY_OUTPUT = APP_DIR / "output" / "MH3U_Supply_Mod" / "romfs"
LIBRARY_DIR = APP_DIR / "library"
QUEST_TYPES = [("MH3U quest", "*.mh3uq *.quest"), ("All files", "*.*")]
EVENT_PACKS = ("quest1", "quest2", "quest3")
CHALLENGE_PACKS = ("quest4",)


def open_folder(path) -> None:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.startfile(str(path))                         # Windows
    except AttributeError:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def short_path(p, n=70) -> str:
    s = str(p)
    return s if len(s) <= n else "..." + s[-(n - 3):]


def pack_label(name: str) -> str:
    return f"Pack {name[-1]}" if name and name[-1].isdigit() else str(name)


def slot_label(key: str) -> str:
    pack, slot = key.split(":")
    return f"{pack_label(pack)}, slot {int(slot) + 1}"


# ================================================================ quest list
class QuestList(ttk.Frame):
    """A searchable table of quests with an action bar.

    kind: "packs" (``packs`` = the pack files shown), "library" or "rom".
    """

    def __init__(self, parent, app, kind, packs=None):
        super().__init__(parent)
        self.app, self.kind, self.packs = app, kind, packs
        bar = ttk.Frame(self, padding=(10, 8, 10, 0))
        bar.pack(fill="x")
        self.q = tk.StringVar()
        sb = SearchBox(bar, self.q, width=34)
        sb.pack(side="left")
        self.search_entry = sb.entry
        Tooltip(sb.entry, "Search by quest name, monster or map (Ctrl+F)")
        self.q.trace_add("write", lambda *_: self.refresh())
        self.show_free = tk.BooleanVar(value=True)
        if kind == "packs":
            ttk.Checkbutton(bar, text="Show free slots", variable=self.show_free,
                            command=self.refresh).pack(side="left", padx=12)
        self.count = ttk.Label(bar, text="", style="Muted.TLabel")
        self.count.pack(side="right")
        body = ttk.Frame(self, padding=(10, 6))
        body.pack(fill="both", expand=True)
        cols = ("name", "star", "map", "monsters")
        self.tree = ttk.Treeview(body, columns=cols, selectmode="browse")
        first = {"packs": "Slot", "library": "", "rom": ""}[kind]
        for col, text, w, stretch in (("#0", first, 92 if kind == "packs" else 64, False),
                                      ("name", "Quest", 320, True), ("star", "Rank", 96, False),
                                      ("map", "Map", 150, False), ("monsters", "Monsters", 320, True)):
            self.tree.heading(col, text=text, anchor="w")
            self.tree.column(col, width=w, anchor="w", stretch=stretch, minwidth=40)
        c = theme.current()
        self.tree.tag_configure("free", foreground=c["free"])
        self.tree.tag_configure("modified", foreground=c["accent"])
        self.tree.tag_configure("group", font=theme.FONTS["h3"], background=c["group"])
        sb = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self.update_actions())
        self.tree.bind("<Double-Button-1>", lambda _e: self.app.edit_selected())
        self.tree.bind("<Return>", lambda _e: self.app.edit_selected())
        self.actions = ttk.Frame(self, padding=(10, 0, 10, 10))
        self.actions.pack(fill="x")
        self.buttons: dict[str, ttk.Button] = {}

    def source(self):
        return self.app.sources.get(self.kind)

    def selected(self):
        s = self.tree.selection()
        return s[0] if s and not s[0].startswith("g:") else None

    # ----------------------------------------------------------- table
    def refresh(self, select=None):
        src = self.source()
        keep = select or self.selected()
        self.tree.delete(*self.tree.get_children())
        if src is None:
            self.count.configure(text="")
            self.update_actions()
            return
        flt = self.q.get().strip().lower()
        dev = self.app.dev_mode.get()
        groups: dict[str, list] = {}
        for e in src.entries():
            if self.packs and e.group not in self.packs:
                continue
            groups.setdefault(e.group, []).append(e)
        shown = 0
        icons = self.app.icons
        for gname, entries in groups.items():
            gid = "g:" + gname
            if self.kind == "packs":
                used = sum(1 for e in entries if e.quest is not None)
                self.tree.insert("", "end", iid=gid, text=pack_label(gname), open=True, tags=("group",),
                                 values=(f"{used} of {len(entries)} slots used"
                                         + (f"   (file {gname})" if dev else ""), "", "", ""))
            elif self.kind == "rom":
                self.tree.insert("", "end", iid=gid, text="", open=True, tags=("group",),
                                 values=(src.group_summary(gname), "", "", ""))
            else:
                gid = ""
            for e in entries:
                if e.quest is None:
                    if not self.show_free.get() or flt:
                        continue
                    self.tree.insert(gid, "end", iid=e.key, text=f" {e.slot}", image=icons.blank(27),
                                     values=("Free slot", "", "", ""), tags=("free",))
                    continue
                q = e.quest
                mons = [m["Type"] for m in q.monsters if m["Type"]]
                names = ", ".join(dict.fromkeys(G.mon_name(m) for m in mons)) or "-"
                name = q.get_text("name", 0) or "(untitled)"
                if dev:
                    name = f"#{q.get('quest_no')}  {name}"
                hay = f"{name} {names} {G.map_name(q.get('map'))} {q.get('quest_no')}".lower()
                if flt and flt not in hay:
                    continue
                first = f" {e.slot}" if self.kind == "packs" else ""
                self.tree.insert(gid, "end", iid=e.key, text=first, image=icons.quest(q, 27),
                                 values=(("* " if e.modified else "") + name, stars(q.get("star")),
                                         G.map_name(q.get("map")), names),
                                 tags=("modified",) if e.modified else ())
                shown += 1
        self.count.configure(text=f"{shown} quest{'s' if shown != 1 else ''}")
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)
            self.tree.see(keep)
        self.update_actions()

    # ----------------------------------------------------------- actions
    def build_actions(self):
        for w in self.actions.winfo_children():
            w.destroy()
        a = self.app
        if self.kind == "packs":
            spec = [("edit", "Edit", a.edit_selected, True),
                    ("new", "New quest here...", a.new_quest, False),
                    ("put", "Put a quest here...", a.put_quest_here, False),
                    ("dup", "Duplicate...", a.duplicate, False),
                    ("tolib", "Copy to my library", a.to_library, False),
                    ("export", "Export...", a.export_quest, False),
                    ("clear", "Clear slot", a.clear_slot, False)]
        elif self.kind == "library":
            spec = [("edit", "Edit", a.edit_selected, True),
                    ("new", "New quest...", a.new_library_quest, False),
                    ("dup", "Duplicate", a.duplicate_library, False),
                    ("togame", "To game...", a.send_to_game, False),
                    ("import", "Import...", a.import_to_library, False),
                    ("export", "Export...", a.export_quest, False),
                    ("delete", "Delete", a.delete_library, False)]
        else:
            spec = [("edit", "Edit", a.edit_selected, True),
                    ("tolib", "Copy to my library", a.to_library, False),
                    ("revert", "Undo my changes", a.revert_rom, False)]
        self.buttons = {}
        for key, text, cmd, accent in spec:
            b = ttk.Button(self.actions, text=text, command=cmd,
                           style="Accent.TButton" if accent else "TButton")
            b.pack(side="left", padx=(0, 6))
            self.buttons[key] = b
        self.update_actions()

    def update_actions(self):
        src = self.source()
        key = self.selected()
        q = src.get(key) if (src and key) else None
        free = src is not None and key is not None and q is None
        rules = {"edit": q is not None,
                 "new": src is not None and (self.kind == "library" or free or bool(self.app.free_slots(self.packs))),
                 "put": key is not None, "dup": q is not None, "tolib": q is not None,
                 "export": q is not None, "clear": q is not None, "togame": q is not None,
                 "delete": q is not None, "import": src is not None,
                 "revert": q is not None and self.kind == "rom" and key is not None and int(key) in src.modified}
        for k, b in self.buttons.items():
            b.state(["!disabled"] if rules.get(k, True) else ["disabled"])


def status_card(parent):
    return ttk.Frame(parent, style="Box.TFrame", padding=(14, 10))


# =================================================================== pages
class InGamePage(ttk.Frame):
    """Your save's quests: Event / Challenge tabs and Backups (as MH4U's In-game page)."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.status = status_card(self)
        self.status.pack(fill="x", padx=10, pady=(10, 4))
        self.nb = ttk.Notebook(self, style="Sub.TNotebook")
        self.nb.pack(fill="both", expand=True, padx=10, pady=(4, 0))
        self.event = QuestList(self.nb, app, "packs", EVENT_PACKS)
        self.challenge = QuestList(self.nb, app, "packs", CHALLENGE_PACKS)
        self.backups = BackupsPanel(self.nb, app)
        self.nb.add(self.event, text="Event quests")
        self.nb.add(self.challenge, text="Challenge quests")
        self.nb.add(self.backups, text="Backups")
        self.nb.bind("<<NotebookTabChanged>>", lambda _e: self._tab_changed())
        note = ttk.Frame(self.challenge, padding=(10, 0, 10, 6))
        note.pack(fill="x", before=self.challenge.actions)
        ttk.Label(note, text="Pack 4 holds the game's Challenge quests. Put your custom quests in "
                             "the Event quests tab (packs 1 to 3).", style="Muted.TLabel").pack(side="left")
        info(note, H.tip("challenge")).pack(side="left", padx=4)

    def lists(self):
        return (self.event, self.challenge)

    def current(self):
        sel = self.nb.select()
        if sel == str(self.challenge):
            return self.challenge
        if sel == str(self.backups):
            return None
        return self.event

    def _tab_changed(self):
        cur = self.current()
        if cur is None:
            self.backups.fill()
        else:
            cur.refresh()

    def build_status(self):
        for w in self.status.winfo_children():
            w.destroy()
        src = self.app.sources["packs"]
        f = self.status
        if src is None:
            ttk.Label(f, text="Your MH3U save was not found yet", style="Card.H2.TLabel").pack(anchor="w")
            ttk.Label(f, style="Card.Muted.TLabel", wraplength=900, justify="left", text=(
                "Start Monster Hunter 3 Ultimate once in Citra so it creates its event quest files, "
                "close Citra, then press 'Find automatically'. For a real 3DS, copy the game's "
                "extra data to your PC (Checkpoint or JKSM) and choose that folder.")).pack(anchor="w", pady=(2, 6))
            row = ttk.Frame(f, style="Card.TFrame")
            row.pack(anchor="w")
            ttk.Button(row, text="Find automatically", style="Accent.TButton",
                       command=self.app.find_packs).pack(side="left")
            ttk.Button(row, text="Choose the folder myself...", command=self.app.choose_packs).pack(side="left", padx=6)
            return
        ev_used = sum(len(src.packs[n].used_slots()) for n in EVENT_PACKS if n in src.packs)
        ev_free = sum(len(src.packs[n].free_slots()) for n in EVENT_PACKS if n in src.packs)
        top = ttk.Frame(f, style="Card.TFrame")
        top.pack(fill="x")
        StatusDot(top, "ok", "card").pack(side="left", padx=(0, 6))
        ttk.Label(top, text=f"Save found: {ev_used} event quests, {ev_free} free event slots",
                  style="Card.H2.TLabel").pack(side="left")
        ttk.Label(f, text=short_path(src.folder, 120), style="Card.Muted.TLabel").pack(anchor="w")
        row = ttk.Frame(f, style="Card.TFrame")
        row.pack(fill="x", pady=(6, 0))
        ttk.Button(row, text="Reload", command=self.app.reload_packs).pack(side="left")
        ttk.Button(row, text="Change folder...", command=self.app.choose_packs).pack(side="left", padx=6)
        ttk.Button(row, text="Open folder", command=lambda: open_folder(src.folder)).pack(side="left")
        ttk.Button(row, text="Back up now", command=self.app.backup_now).pack(side="left", padx=6)
        ttk.Label(row, text="Close Citra before saving: it rewrites these files when it exits.",
                  style="Card.Muted.TLabel").pack(side="right")


class ListPage(ttk.Frame):
    """Library or base-game page: a status card above a quest list."""

    def __init__(self, parent, app, kind):
        super().__init__(parent)
        self.app, self.kind = app, kind
        self.status = status_card(self)
        self.status.pack(fill="x", padx=10, pady=(10, 0))
        self.list = QuestList(self, app, kind)
        self.list.pack(fill="both", expand=True)

    def build_status(self):
        for w in self.status.winfo_children():
            w.destroy()
        src = self.app.sources.get(self.kind)
        f = self.status
        if self.kind == "library":
            n = len(src.quests) if src else 0
            ttk.Label(f, text=f"Quest library: {n} quest{'s' if n != 1 else ''}",
                      style="Card.H2.TLabel").pack(anchor="w")
            ttk.Label(f, style="Card.Muted.TLabel", wraplength=950, justify="left", text=(
                "Quests kept on your PC, one .mh3uq file each. Edit them here; 'To game...' puts a "
                "quest into an event slot of your save. The files can be shared.")).pack(anchor="w")
            row = ttk.Frame(f, style="Card.TFrame")
            row.pack(anchor="w", pady=(6, 0))
            ttk.Button(row, text="Open the library folder", command=lambda: open_folder(LIBRARY_DIR)).pack(side="left")
            return
        if src is None:
            ttk.Label(f, text="Base-game quests (optional)", style="Card.H2.TLabel").pack(anchor="w")
            ttk.Label(f, style="Card.Muted.TLabel", wraplength=950, justify="left", text=(
                "Edit the game's own Village and Port quests. This needs the 'romfs' folder of your "
                "extracted game. Your ROM is never changed: the editor writes a mod folder that Citra "
                "(or Luma on a 3DS) loads instead.")).pack(anchor="w", pady=(2, 6))
            ttk.Button(f, text="Choose the extracted romfs folder...", style="Accent.TButton",
                       command=self.app.choose_romfs).pack(anchor="w")
            return
        ttk.Label(f, text=f"Base-game quests: {len(src.quests)} quests, {len(src.modified)} edited",
                  style="Card.H2.TLabel").pack(anchor="w")
        ttk.Label(f, text=short_path(src.romfs, 120), style="Card.Muted.TLabel").pack(anchor="w")
        row = ttk.Frame(f, style="Card.TFrame")
        row.pack(anchor="w", pady=(6, 0))
        ttk.Button(row, text="Install the mod into Citra", command=self.app.install_rom_mod).pack(side="left")
        ttk.Button(row, text="Open the mod folder", command=lambda: open_folder(ROM_OUTPUT.parent)).pack(side="left", padx=6)
        ttk.Button(row, text="Change folder...", command=self.app.choose_romfs).pack(side="left")

# ========================================================== monster pack
class MonsterPackPage(ttk.Frame):
    """ROM hack: let any large monster appear on any map (see monsterpack.py)."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        outer = ttk.Frame(self, padding=(10, 10, 10, 0))
        outer.pack(fill="both", expand=True)
        warn = ttk.Frame(outer, style="Box.TFrame", padding=(14, 10))
        warn.pack(fill="x")
        ttk.Label(warn, text="Monster placement pack  -  ROM hack, read this first", style="Card.H2.TLabel").pack(anchor="w")
        ttk.Label(warn, style="Card.Danger.TLabel", wraplength=1150, justify="left", text=(
            "This pack changes how the game works: it adds a small patch to the game's code (exefs/code.ips) and "
            "replaces the files of the monsters that need new map data (romfs/arc/enemy). It is built from YOUR extracted game, on your "
            "computer, and installed as a mod: your ROM and your save are not modified, and removing the mod "
            "brings the game back exactly as it was.")).pack(anchor="w", pady=(4, 0))
        ttk.Label(warn, style="Card.Muted.TLabel", wraplength=1150, justify="left", text=(
            "- Only Zinogre on Sandy Plains has been tested in the game. The other combinations follow the same "
            "rules but are untested: a monster may get stuck, behave oddly, or crash the game when the quest "
            "loads. Test a quest in Citra before playing it seriously.\n"
            "- Water arenas, Sacred Land, Tower, the siege maps (Great Desert, Underwater Ruin, Tainted Sea) and "
            "the bosses Alatreon and Dire Miralis away from their own maps are the most likely to go wrong. "
            "Ceadeus and Jhen Mohran (and their variants) stay on their own maps.\n"
            "- Multiplayer: every player must install the same pack. Built from the same game version it is "
            "identical for everybody: compare the fingerprint below. A player without it does not see the monster.\n"
            "- Big sizes: the pack also extends the game's size table, so a quest can make a monster up to "
            "2000 % (Developer mode, 'Size %' above 255). Untested in the game: a giant may clip through "
            "walls or be hard to reach.\n"
            "- Back up your save before trying (Backups button). The pack can not be combined with another "
            "code mod (code.ips / code.bin).")).pack(anchor="w", pady=(4, 0))
        self.status = status_card(outer)
        self.status.pack(fill="x", pady=(8, 0))
        ttk.Label(outer, text="Which maps each monster can start on   (\u25cf in the game   + added by the pack   "
                              "+! added, higher risk)", style="H3.TLabel").pack(anchor="w", pady=(10, 2))
        box = ttk.Frame(outer)
        box.pack(fill="both", expand=True, pady=(0, 10))
        self.maps = [m for m in sorted(G.MAP_NAMES) if G.MAP_TO_INTERNAL.get(m)]
        cols = [f"m{m}" for m in self.maps]
        self.tree = ttk.Treeview(box, columns=cols, show="tree headings", style="Small.Treeview", height=14)
        self.tree.heading("#0", text="Monster")
        short = {1: "Island", 2: "Sandy", 3: "Forest", 4: "Tundra", 5: "Volcano", 6: "Desert", 7: "Ruin",
                 8: "Arena", 10: "W.Arena ev.", 11: "Sacred", 12: "W.Arena", 13: "Misty", 14: "Tower",
                 15: "T.Sea"}
        try:
            from tkinter import font as tkfont
            hfont = tkfont.nametofont("TkHeadingFont")
        except (tk.TclError, ImportError):
            hfont = None
        self.tree.column("#0", width=160, stretch=False)
        for m, c in zip(self.maps, cols):
            text = short.get(m, G.map_name(m))
            width = max(52, hfont.measure(text) + 14) if hfont else 70
            self.tree.heading(c, text=text)
            self.tree.column(c, width=width, minwidth=width, anchor="center", stretch=True)
        ttk.Label(outer, style="Muted.TLabel", wraplength=1200, justify="left", text="   ".join(
            f"{short.get(m, G.map_name(m))} = {G.map_name(m)}" for m in self.maps)).pack(side="bottom", anchor="w",
                                                                                  pady=(0, 6), before=box)
        sb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.refresh()

    def refresh(self):
        app = self.app
        for w in self.status.winfo_children():
            w.destroy()
        f = self.status
        built = monsterpack.read_manifest(app.monster_pack_dir())
        inst, where = app.installed_monster_pack()
        ttk.Label(f, text=f"Game version: {G.region_name()}  ({G.TITLE_ID})", style="Card.H2.TLabel").pack(anchor="w")
        romfs = app.romfs_dir()
        ttk.Label(f, style="Card.Muted.TLabel", text="Extracted game: " + (short_path(romfs, 110) if romfs else
                  "not set (Settings > Choose the romfs folder; exefs/code.bin must be next to romfs)")).pack(anchor="w")
        ttk.Label(f, style="Card.TLabel" if built else "Card.Muted.TLabel", text=(
            f"Pack built: {len(built.get('added', []))} monster/map combinations added for "
            f"{len(built.get('monsters', []))} monsters"
            + (", sizes up to 2000 %" if built.get("big_sizes") else ", without big sizes (rebuild it)")
            + f".  Fingerprint {built.get('fingerprint')}"
            if built else "Pack not built yet.")).pack(anchor="w", pady=(4, 0))
        if inst:
            same = built and built.get("fingerprint") == inst.get("fingerprint")
            ttk.Label(f, style="Card.Ok.TLabel" if same or not built else "Card.Warn.TLabel", text=(
                f"Installed in {short_path(where, 90)}  (fingerprint {inst.get('fingerprint')}"
                + (")" if same or not built else ", different from the pack you built: install again)"))).pack(anchor="w")
        else:
            ttk.Label(f, style="Card.Muted.TLabel", text="Not installed in Citra. On a real 3DS, copy the pack "
                      f"folder's content into luma/titles/{G.TITLE_ID}/ (game patching enabled in Luma)."
                      ).pack(anchor="w")
        row = ttk.Frame(f, style="Card.TFrame")
        row.pack(anchor="w", pady=(6, 0))
        self.build_btn = ttk.Button(row, text="Build the pack from my game", style="Accent.TButton",
                                    command=app.build_monster_pack)
        self.build_btn.pack(side="left")
        ttk.Button(row, text="Install in Citra", command=app.install_monster_pack,
                   state="normal" if built else "disabled").pack(side="left", padx=6)
        ttk.Button(row, text="Remove from Citra", command=app.remove_monster_pack,
                   state="normal" if inst else "disabled").pack(side="left")
        ttk.Button(row, text="Open the pack folder", command=lambda: open_folder(app.monster_pack_dir()),
                   state="normal" if built else "disabled").pack(side="left", padx=6)
        self.progress = ttk.Label(f, text="", style="Card.Muted.TLabel")
        self.progress.pack(anchor="w")
        self.fill(inst or built)

    def fill(self, manifest):
        self.tree.delete(*self.tree.get_children())
        for em in sorted(G.MONSTERS):
            if not monsterpack.is_large(em):
                continue
            vals = []
            for m in self.maps:
                st, _p = monsterpack.pair_status(em, m, manifest)
                if st == "native":
                    vals.append("\u25cf")
                elif st == "pack":
                    vals.append("+!" if monsterpack.risk_notes(em, m) else "+")
                else:
                    vals.append("")
            self.tree.insert("", "end", text=G.mon_name(em), values=vals)


# ================================================================ backups
class BackupsPanel(ttk.Frame):
    """Full backups of the save's quest files and copies of every replaced quest."""

    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        ttk.Label(self, style="Muted.TLabel", wraplength=1050, justify="left", text=(
            "Every save first copies the four quest files of your save (full backup) and keeps a "
            "separate copy of every quest it replaces, edits or clears. Restoring also backs up the "
            "current files first, so nothing is lost. Old backups are cleaned up automatically (Settings), "
            "but these are never deleted: your original files, the very first full backup, and the first "
            "copy of every quest (marked with a lock).")).pack(anchor="w", pady=(0, 4))
        self.usage = ttk.Label(self, style="Muted.TLabel", text="")
        self.usage.pack(anchor="w", pady=(0, 8))
        cols = ttk.Frame(self)
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=3)
        cols.columnconfigure(1, weight=2)
        cols.rowconfigure(0, weight=1)
        left = ttk.Frame(cols, style="Box.TFrame", padding=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ttk.Label(left, text="Replaced quests", style="Card.H3.TLabel").pack(anchor="w")
        self.quests = ttk.Treeview(left, columns=("where", "reason"), height=10, selectmode="browse")
        for col, text, w in (("#0", "Quest", 300), ("where", "Was in", 130), ("reason", "Saved", 200)):
            self.quests.heading(col, text=text, anchor="w")
            self.quests.column(col, width=w, anchor="w")
        self.quests.pack(fill="both", expand=True, pady=6)
        r = ttk.Frame(left, style="Card.TFrame")
        r.pack(fill="x")
        ttk.Button(r, text="Put it back in its slot", style="Accent.TButton",
                   command=self._restore_quest).pack(side="left")
        ttk.Button(r, text="To library", command=self._to_library).pack(side="left", padx=6)
        right = ttk.Frame(cols, style="Box.TFrame", padding=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ttk.Label(right, text="Full backups", style="Card.H3.TLabel").pack(anchor="w")
        self.full = ttk.Treeview(right, columns=("reason",), style="Small.Treeview", height=10,
                                 selectmode="browse")
        self.full.heading("#0", text="Date", anchor="w")
        self.full.heading("reason", text="Made", anchor="w")
        self.full.column("#0", width=160)
        self.full.column("reason", width=200)
        self.full.pack(fill="both", expand=True, pady=6)
        r = ttk.Frame(right, style="Card.TFrame")
        r.pack(fill="x")
        ttk.Button(r, text="Restore this backup", command=self._restore_full).pack(side="left")
        ttk.Button(r, text="Open folder", command=lambda: open_folder(app.backups.root)).pack(side="left", padx=6)
        self._full, self._quests = [], []

    def fill(self):
        b = self.app.backups
        self.usage.configure(text=f"Space used by the backups: {b.size() / 1048576:.1f} MB. Kept: the "
                                  f"{b.keep_full} most recent full backups and the {b.keep_per_quest} most recent "
                                  "copies of each quest, plus the protected ones.")
        self.full.delete(*self.full.get_children())
        self._full = b.list_full()
        first = b.protected_full()
        for i, s in enumerate(self._full):
            lock = "\U0001F512 " if s["kind"] == "original" or s["path"] == first else ""
            self.full.insert("", "end", iid=str(i), text=lock + s["time"],
                             values=(s["reason"] + ("  (first backup, never deleted)" if s["path"] == first else ""),))
        self.quests.delete(*self.quests.get_children())
        self._quests = self.app.backups.list_quests()
        for i, s in enumerate(self._quests):
            try:
                img = self.app.icons.quest(Quest(Path(s["path"]).read_bytes()), 27)
            except (OSError, QuestFormatError):
                img = self.app.icons.blank(27)
            where = f"{pack_label(s.get('pack', '?'))}, slot {s.get('slot', '?')}"
            lock = "  \U0001F512" if s.get("protected") else ""
            self.quests.insert("", "end", iid=str(i), text="  " + s.get("name", "?") + lock, image=img,
                               values=(where, f"{s.get('time', '')}  ({s.get('reason', '')})"))

    def _restore_full(self):
        sel = self.full.selection()
        packs = self.app.sources["packs"]
        if not sel or packs is None:
            return
        snap = self._full[int(sel[0])]
        if packs.dirty() and not messagebox.askyesno(APP_TITLE, "You have unsaved changes; they will be lost. Continue?", parent=self):
            return
        if not messagebox.askyesno(APP_TITLE, f"Replace your save's quest files with the backup of "
                                   f"{snap['time']}?\n\nClose Citra first. The current files are backed "
                                   "up before.", parent=self):
            return
        self.app.backups.restore_full(snap["path"], packs.folder)
        packs.reload()
        self.app.title(APP_TITLE)
        self.app.reload_lists()
        self.app.set_status(f"Quest files restored from the backup of {snap['time']}.")

    def _selected_quest(self):
        sel = self.quests.selection()
        return self._quests[int(sel[0])] if sel else None

    def _restore_quest(self):
        b = self._selected_quest()
        packs = self.app.sources["packs"]
        if b is None or packs is None:
            return
        key = f"{b.get('pack')}:{int(b.get('slot', 1)) - 1}"
        if key.split(":")[0] not in packs.packs:
            return
        if packs.get(key) is not None and not messagebox.askyesno(
                APP_TITLE, f"{slot_label(key)} holds another quest now. Replace it? (that quest is "
                "backed up when you save)", parent=self):
            return
        try:
            packs.restore_quest(key, Path(b["path"]).read_bytes())
        except (PackError, OSError, QuestFormatError) as exc:
            messagebox.showerror(APP_TITLE, str(exc), parent=self)
            return
        self.app.mark_unsaved()
        self.app.reload_lists()
        self.app.set_status(f"Quest put back in {slot_label(key)} - save to write it to the game.")

    def _to_library(self):
        b = self._selected_quest()
        if b is None or self.app.sources["library"] is None:
            return
        try:
            self.app.sources["library"].add(Quest(Path(b["path"]).read_bytes()))
        except (OSError, QuestFormatError) as exc:
            messagebox.showerror(APP_TITLE, str(exc), parent=self)
            return
        self.app.reload_lists()
        self.app.set_status("Copied to your quest library.")


# =================================================================== guide
class GuidePage(ttk.Frame):
    """The built-in guide: one tab per topic (text in guide.py, the same text is in docs/GUIDE.md)."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        head = ttk.Frame(self, padding=(24, 14, 24, 0))
        head.pack(fill="x")
        ttk.Label(head, text="Guide", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text=f"{APP_TITLE} {__version__}", style="Muted.TLabel").pack(side="right")
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=16, pady=(8, 8))
        for title, sections in guide.pages():
            page = ttk.Frame(self.nb)
            self.nb.add(page, text=title)
            sf = ScrollFrame(page)
            sf.pack(fill="both", expand=True)
            body = ttk.Frame(sf.inner, padding=(14, 6))
            body.pack(fill="both", expand=True)
            for heading, text in sections:
                card = ttk.Frame(body, style="Box.TFrame", padding=(14, 10))
                card.pack(fill="x", pady=(8, 0))
                ttk.Label(card, text=heading, style="Card.H3.TLabel").pack(anchor="w")
                if text:
                    ttk.Label(card, text=text, style="Card.TLabel", wraplength=980, justify="left").pack(
                        anchor="w", pady=(4, 0))
            if title == "Game values":
                self._strength_table(body)
            if title == "Getting started":
                ttk.Label(body, text="\nQuest format research: mh3u-quest-studio (MIT)  ·  not affiliated with "
                                     "Capcom or Nintendo.", style="Muted.TLabel").pack(anchor="w")

    def _strength_table(self, body):
        app = self.app
        card = ttk.Frame(body, style="Box.TFrame", padding=(14, 10))
        card.pack(fill="x", pady=(8, 0))
        ttk.Label(card, text="Typical values of the game's own quests, by hub and star rank",
                  style="Card.H3.TLabel").pack(anchor="w")
        ttk.Label(card, style="Card.Muted.TLabel", wraplength=980, justify="left", text=(
            "Health, Attack and Toughness are rows of the game's difficulty table, not percentages. "
            "Median values for each hub and rank:")).pack(anchor="w", pady=(2, 6))
        grid = ttk.Frame(card, style="Card.TFrame")
        grid.pack(anchor="w")
        heads = ["Quests", "Health ×", "Attack ×", "Damage taken ×", "Fee", "Reward", "HR points"]
        if app.dev_mode.get():
            heads.append("Rows (H / A / T)")
        for c_, h in enumerate(heads):
            ttk.Label(grid, text=h, style="Card.TLabel", font=theme.FONTS["bold"]).grid(
                row=0, column=c_, sticky="w", padx=(0, 20))
        for r, k in enumerate(H.group_keys(), start=1):
            g = H.GROUPS[k]
            vals = [H.group_label(k), f"{g['hp']:g}", f"{g['atk']:g}", f"{g['dmg']:g}",
                    f"{g['fee']:,}z", f"{g['reward']:,}z", f"{g['hrp']:,}"]
            if app.dev_mode.get():
                vals.append(f"{g['hp_row']} / {g['at_row']} / {g['df_row']}")
            for c_, v in enumerate(vals):
                ttk.Label(grid, text=v, style="Card.TLabel").grid(row=r, column=c_, sticky="w", padx=(0, 20))


# ===================================================================== app
class App(tk.Tk):
    def __init__(self):
        i18n.install()
        super().__init__()
        self.withdraw()
        self.settings = Settings()
        i18n.set_language(self.settings.get("language") or i18n.system_language())
        G.set_names_language(i18n.LANG)
        self.title(APP_TITLE)
        self.geometry("1280x840")
        self.minsize(1080, 680)
        self.dev_mode = tk.BooleanVar(value=bool(self.settings.get("dev_mode", False)))
        Tooltip.enabled = bool(self.settings.get("tooltips", True))
        theme.apply(self, self.settings.get("theme", theme.DEFAULT_THEME))
        disable_wheel_value_changes(self)
        self.icons = Icons(self)
        if self.icons.app_icon():
            self.iconphoto(True, self.icons.app_icon())
        ico = ASSETS / "app_icon.ico"
        if sys.platform == "win32" and ico.is_file():
            try:                                   # window, title bar and taskbar icon on Windows
                self.iconbitmap(default=str(ico))
            except tk.TclError:
                pass
        G.set_region(self._initial_region())
        self.backups = self._make_backups()
        self.boxes = CustomBoxes(APP_DIR / "custom_supply.json")
        self.sources: dict = {"packs": None, "library": None, "rom": None}
        self.page = "ingame"
        self.edit_kind = None
        self._base_cache = None
        self._warned = False
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_all("<Control-s>", lambda _e: self.save())
        self.bind_all("<Control-f>", lambda _e: self.find_here())
        self.load_sources()
        self.build_ui()
        self.deiconify()
        self.after(200, self.first_run)

    # ---------------------------------------------------------------- errors
    def report_callback_exception(self, exc, val, tb):
        text = "".join(traceback.format_exception(exc, val, tb))
        try:
            (APP_DIR / "error_log.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
        messagebox.showerror(APP_TITLE, f"Unexpected error:\n\n{val}\n\nDetails were saved in error_log.txt")

    # ---------------------------------------------------------- game version
    def _initial_region(self) -> str:
        """The version chosen in the settings; for a first start (or a 1.0 settings file) it is
        guessed from the saves and extracted game already known, EU otherwise."""
        r = self.settings.get("region")
        if r in G.REGIONS:
            return r
        from .monsterpack import detect_region
        r = pack_dir_region(self.settings.get("pack_dir"))
        if r is None and self.settings.get("romfs"):
            r = detect_region(self.settings.get("romfs"))
        if r is None:
            saves = regions_with_saves()
            r = saves[0] if len(saves) == 1 else "eu"
        self.settings.set("region", r)
        return r

    def _make_backups(self):
        from .backup import KEEP_FULL, KEEP_PER_QUEST
        return Backups(keep_full=int(self.settings.get("keep_full", KEEP_FULL)),
                       keep_per_quest=int(self.settings.get("keep_per_quest", KEEP_PER_QUEST)))

    def setting_key(self, name: str) -> str:
        """Paths are remembered per game version (the EU keys keep their 1.0 names)."""
        return name if G.REGION == "eu" else f"{name}_{G.REGION}"

    def romfs_dir(self):
        return self.settings.get(self.setting_key("romfs"))

    def switch_region(self, region: str) -> bool:
        if region == G.REGION or region not in G.REGIONS:
            return False
        if self.editor.winfo_ismapped() and not self.editor.leave():
            return False
        dirty = self.dirty_sources()
        if dirty and not messagebox.askyesno(APP_TITLE, "You have unsaved changes; they will be lost. "
                                             "Switch the game version anyway?", parent=self):
            return False
        G.set_region(region)
        self.settings.set("region", region)
        self.forget_monster_pack()
        self.backups = self._make_backups()
        self.sources = {"packs": None, "library": None, "rom": None}
        self._base_cache = None
        self.load_sources()
        self.build_ui()
        self.set_status(f"Game version: {G.region_name()}. "
                        + ("Save found." if self.sources["packs"] else "No save of this version was found yet."))
        return True

    # --------------------------------------------------------------- sources
    def load_sources(self):
        romfs = self.romfs_dir()
        base = read_base_numbers(romfs) if romfs and Path(romfs).is_dir() else set()
        pack = self.settings.get(self.setting_key("pack_dir"))
        if pack_dir_region(pack) not in (None, G.REGION):
            pack = None                            # a save of the other version
        if pack and Path(pack).is_dir():
            self._set_packs(pack, base, quiet=True)
        if self.sources["packs"] is None:
            found = find_emulator_pack_dirs()
            if found:
                self._set_packs(found[0], base, quiet=True)
        try:
            self.sources["library"] = LibrarySource(LIBRARY_DIR)
        except OSError:
            self.sources["library"] = None
        if romfs and Path(romfs).is_dir():
            try:
                self.sources["rom"] = RomSource(romfs)
            except (PackError, OSError, ValueError):
                self.sources["rom"] = None

    def _set_packs(self, folder, base=None, quiet=False) -> bool:
        found = find_pack_dir(folder)
        if found is None:
            if not quiet:
                messagebox.showerror(APP_TITLE, "No quest files (quest1 ... quest4) were found in that folder.\n\n"
                                     "Choose your Citra folder, its 'sdmc' folder, or the folder that "
                                     "contains quest1 ... quest4.")
            return False
        try:
            self.sources["packs"] = PackSource(found, self.backups,
                                               reserved=base if base is not None else self._base_numbers())
        except (PackError, OSError, ValueError) as exc:
            if not quiet:
                messagebox.showerror(APP_TITLE, str(exc))
            return False
        self.settings.set(self.setting_key("pack_dir"), str(found))
        return True

    def _base_numbers(self):
        romfs = self.romfs_dir()
        return read_base_numbers(romfs) if romfs and Path(romfs).is_dir() else set()

    def source_can_create(self):
        src = self.sources.get(self.edit_kind)
        return bool(src and src.kind == "packs")

    # -------------------------------------------------------------------- UI
    def build_ui(self):
        for w in self.winfo_children():
            if not isinstance(w, tk.Toplevel):
                w.destroy()
        head = ttk.Frame(self, style="Header.TFrame", padding=(10, 6))
        head.pack(fill="x")
        TribalBand(self).pack(fill="x")
        if self.icons.app_icon():
            ttk.Label(head, image=self.icons.app_icon(), style="Header.TLabel").pack(side="left")
        ttk.Label(head, text=APP_TITLE, style="Header.TLabel").pack(side="left", padx=(8, 22))
        self.nav = {}
        for page, text in (("ingame", "In-game quests"), ("library", "Quest library"),
                           ("rom", "Base game"), ("pack", "Monster pack"), ("guide", "Guide")):
            b = ttk.Button(head, text=text, style="Nav.TButton", width=0, command=lambda p=page: self.show_page(p))
            b.pack(side="left", padx=1)
            self.nav[page] = b
        ttk.Button(head, text="Settings", style="Header.TButton", width=0, command=self.open_settings).pack(side="right")
        ttk.Button(head, text="Backups", style="Header.TButton", width=0, command=self.open_backups).pack(side="right")
        ttk.Button(head, text="Supply boxes", style="Header.TButton", width=0, command=self.open_boxes).pack(side="right")
        dm = ttk.Checkbutton(head, text="Developer mode", variable=self.dev_mode, style="Header.TCheckbutton",
                             command=self.toggle_dev)
        dm.pack(side="right", padx=10)
        Tooltip(dm, H.tip("dev_mode"))
        self.statusbar = ttk.Label(self, text="", style="Muted.TLabel", padding=(10, 3))
        self.statusbar.pack(side="bottom", fill="x")
        self.finder = Finder(self, self.find_scope)
        self.content = ttk.Frame(self)
        self.content.pack(fill="both", expand=True)
        self.pages = {"ingame": InGamePage(self.content, self), "library": ListPage(self.content, self, "library"),
                      "rom": ListPage(self.content, self, "rom"), "pack": MonsterPackPage(self.content, self),
                      "guide": GuidePage(self.content, self)}
        self.editor = EditorPage(self.content, self)
        self.reload_lists(show=False)
        self.show_page(self.page)
        self.set_status("Ready." if self.sources["packs"] else "Your MH3U save was not found yet.")

    def all_lists(self):
        return [*self.pages["ingame"].lists(), self.pages["library"].list, self.pages["rom"].list]

    def show_page(self, page):
        if self.editor.winfo_ismapped() and not self.editor.leave():
            return
        self.page = page
        for w in (*self.pages.values(), self.editor):
            w.pack_forget()
        self.pages[page].pack(fill="both", expand=True)
        for k, b in self.nav.items():
            b.configure(style="NavOn.TButton" if k == page else "Nav.TButton")
        ql = self.current_list()
        if ql is not None:
            ql.refresh()
        self.after(60, self.finder.refresh)

    def show_home(self):
        self.show_page({"packs": "ingame", "library": "library", "rom": "rom"}.get(self.edit_kind, self.page))

    def focus_search(self):
        ql = self.current_list()
        if not self.editor.winfo_ismapped() and ql is not None:
            ql.search_entry.focus_set()

    # ------------------------------------------------------------------ Ctrl+F
    def find_scope(self):
        """The part of the window Ctrl+F searches: the open editor tab, or the current page."""
        if self.editor.winfo_ismapped():
            try:
                return self.nametowidget(self.editor.nb.select())
            except (KeyError, tk.TclError):
                return self.editor
        return self.pages.get(self.page)

    def find_here(self):
        """Ctrl+F: quest lists have their own search box; everywhere else the find bar opens."""
        if not self.editor.winfo_ismapped() and self.current_list() is not None:
            focused = self.focus_get()
            if focused is not None and focused is getattr(self.current_list(), "search_entry", None):
                self.finder.open()          # pressed twice: search the text of the page too
            else:
                self.focus_search()
            return
        self.finder.open()

    def set_status(self, text):
        self.statusbar.configure(text=text)

    def current_list(self):
        if self.page == "ingame":
            return self.pages["ingame"].current()
        if self.page in ("library", "rom"):
            return self.pages[self.page].list
        return None

    def toggle_dev(self):
        self.settings.set("dev_mode", bool(self.dev_mode.get()))
        key, kind = self.editor.key, self.edit_kind
        editing = self.editor.winfo_ismapped()
        self.editor.build_tabs()
        old = self.pages["guide"]
        self.pages["guide"] = GuidePage(self.content, self)
        old.destroy()
        for ql in self.all_lists():
            ql.refresh()
        if editing and key is not None:
            self.open_editor(kind, key, keep_snapshot=True)
        elif self.page == "guide":
            self.pages["guide"].pack(fill="both", expand=True)

    def mark_unsaved(self):
        self.title("* " + APP_TITLE)

    # ---------------------------------------------------------------- editing
    def edit_selected(self):
        ql = self.current_list()
        if ql is None:
            return
        key = ql.selected()
        src = ql.source()
        if key is None or src is None:
            return
        if src.get(key) is None:
            if ql.kind == "packs":
                self.new_quest()
            return
        self.open_editor(ql.kind, key)

    def open_editor(self, kind, key, keep_snapshot=False):
        src = self.sources[kind]
        q = src.get(key)
        if q is None:
            return
        self.edit_kind = kind
        back = {"packs": "In-game quests", "library": "Quest library", "rom": "Base game"}[kind]
        if kind == "packs":
            where = slot_label(key)
        elif kind == "library":
            where = "Quest library"
        else:
            where = f"Base game, {H.rank_label(q)}"
        for w in self.pages.values():
            w.pack_forget()
        self.editor.pack(fill="both", expand=True)
        self.editor.open(key, q, where, back, keep_snapshot=keep_snapshot)

    def on_quest_changed(self, key):
        src = self.sources[self.edit_kind]
        src.mark_dirty(key)
        self.mark_unsaved()
        self.set_status("Unsaved changes - press Save (Ctrl+S) to write them.")

    def validate(self, key, quest):
        src = self.sources.get(self.edit_kind)
        if src is None or quest is None:
            return []
        pack, installed = self.monster_pack()
        found = validate_quest(quest, src.numbers_except(key), in_pack=src.kind == "packs",
                               fit_problem=src.fit_problem(key), monster_pack=pack, pack_installed=installed)
        no = quest.get("item_set_no")
        if self.boxes.is_custom(no):
            from .validate import Issue
            found.append(Issue("info", f"This quest uses one of your own supply boxes. It only appears in the "
                                       "game when the editor's supply files are installed (Supply Box tab); "
                                       "otherwise the game opens the box it normally has under that number."))
        return found

    def change_number(self):
        src = self.sources.get(self.edit_kind)
        key = self.editor.key
        q = src.get(key) if src else None
        if q is None or src.kind != "packs":
            return
        n = simpledialog.askinteger("Quest number", f"New quest number (1-99999).\n\n{H.tip('quest_no')}",
                                    initialvalue=q.get("quest_no"), minvalue=1, maxvalue=99999, parent=self)
        if n is None or n == q.get("quest_no"):
            return
        try:
            src.renumber(key, n)
        except PackError as exc:
            messagebox.showerror(APP_TITLE, str(exc), parent=self)
            return
        self.editor.reload_tabs()
        self.editor.changed()

    # ------------------------------------------------------------- templates
    def _base_quests(self):
        if self._base_cache is None:
            self._base_cache = {}
            romfs = self.romfs_dir()
            if romfs and Path(romfs).is_dir():
                try:
                    self._base_cache = RomSource(romfs, load_edits=False).quests
                except (PackError, OSError, ValueError):
                    self._base_cache = {}
        return self._base_cache

    def template_quests(self):
        """(label, quest, category) of every quest that can be copied."""
        out = []
        for kind, cat in (("packs", "In your game"), ("library", "Library")):
            src = self.sources.get(kind)
            if src:
                for e in src.entries():
                    if e.quest is not None:
                        out.append((e.quest.get_text("name", 0), e.quest, cat))
        for no, q in sorted(self._base_quests().items()):
            out.append((q.get_text("name", 0), q, "Game quests"))
        return out

    def pick_template(self, title):
        entries = []
        for i, (label, q, cat) in enumerate(self.template_quests()):
            mons = [m["Type"] for m in q.monsters if m["Type"]]
            what = ", ".join(dict.fromkeys(G.mon_name(m) for m in mons[:3])) or G.objectives_sentence(q)
            rank = H.rank_label(q) if cat == "Game quests" else stars(q.get("star"))
            sub = f"{rank}  ·  {G.map_name(q.get('map'))}  ·  {what}"
            entries.append({"key": i, "name": label, "sub": sub, "cat": cat, "search": f"{label} {sub}",
                            "icon": (lambda q=q: self.icons.quest(q, 54)), "_q": q})
        if not entries:
            messagebox.showinfo(APP_TITLE, "There is no quest to copy yet.", parent=self)
            return None
        cats = [c for c in ("In your game", "Library", "Game quests") if any(e["cat"] == c for e in entries)]
        res = picker._run(self, title=title, entries=entries, tile=(420, 68), icon_size=54, columns=2,
                          categories=cats,
                          note="A new quest starts as an exact copy of the quest you pick. Choose one with the "
                               "same map and similar monsters: some hidden data at the end of a quest depends "
                               "on the map.")
        return None if res is None else entries[res]["_q"]

    def free_slots(self, packs=EVENT_PACKS):
        src = self.sources.get("packs")
        if not src:
            return []
        return [e.key for e in src.entries() if e.quest is None and (not packs or e.group in packs)]

    # ---------------------------------------------------------------- actions
    def _ingame_list(self):
        ql = self.current_list()
        return ql if (ql is not None and ql.kind == "packs") else self.pages["ingame"].event

    def _sel_quest(self):
        ql = self.current_list()
        src = ql.source() if ql else None
        key = ql.selected() if ql else None
        return ql, src, key, (src.get(key) if (src and key) else None)

    def new_quest(self, template=None):
        src = self.sources["packs"]
        if src is None:
            return
        ql = self._ingame_list()
        key = ql.selected()
        if key is None or src.get(key) is not None:
            free = self.free_slots(ql.packs) or self.free_slots(EVENT_PACKS)
            if not free:
                messagebox.showinfo(APP_TITLE, "Every event slot is used. Clear a slot first.", parent=self)
                return
            key = free[0]
        tpl = template or self.pick_template("New quest: choose a quest to copy")
        if tpl is None:
            return
        name = simpledialog.askstring("New quest", "Name of the new quest (all languages):",
                                      initialvalue="My Custom Quest", parent=self)
        if not name:
            return
        try:
            q = src.create(key, tpl, src.next_free_number())
            q.set_text("name", name)
            if spawns.is_bare(q):                 # copied from a base-game quest
                try:
                    spawns.adopt_game_list(q, tpl.get("quest_no"), q.get("star"),
                                           autofill.pool_for_star(q.get("star")),
                                           [e.quest for e in src.entries() if e.quest is not None])
                except QuestFormatError:
                    pass
        except (PackError, ValueError) as exc:
            messagebox.showerror(APP_TITLE, str(exc), parent=self)
            return
        src.mark_dirty(key)
        ql.refresh(select=key)
        self.open_editor("packs", key)
        self.on_quest_changed(key)
        self.set_status(f"New quest created in {slot_label(key)}. Edit it, then save.")

    def duplicate(self):
        ql, _src, _key, q = self._sel_quest()
        if q is None:
            return
        ql.tree.selection_remove(ql.tree.selection())
        self.new_quest(template=q)

    def put_quest_here(self):
        """MH4U's 'Put a quest here': from the library, a quest file or a backup."""
        src = self.sources["packs"]
        ql = self._ingame_list()
        key = ql.selected()
        if src is None or key is None:
            return
        choices = [("library", "From my quest library", "A quest you keep on your PC"),
                   ("file", "From a quest file...", "A .mh3uq or q_NNNNN.quest file"),
                   ("backup", "From a backup", "A quest that an earlier save replaced")]
        entries = [{"key": k, "name": n, "sub": s} for k, n, s in choices]
        how = picker._run(self, title=f"Put a quest in {slot_label(key)}", entries=entries, tile=(340, 54),
                          icon_size=0, columns=1)
        if how is None:
            return
        record = None
        if how == "library":
            lib = self.sources["library"]
            if not lib or not lib.quests:
                messagebox.showinfo(APP_TITLE, "Your quest library is empty.", parent=self)
                return
            items = [{"key": k, "name": q.get_text("name", 0),
                      "sub": f"{stars(q.get('star'))}  {G.map_name(q.get('map'))}",
                      "icon": (lambda q=q: self.icons.quest(q, 54))} for k, q in lib.quests.items()]
            k = picker._run(self, title="Choose a library quest", entries=items, tile=(380, 68),
                            icon_size=54, columns=2)
            if k is None:
                return
            record = lib.get(k).to_bytes()
        elif how == "file":
            path = filedialog.askopenfilename(parent=self, filetypes=QUEST_TYPES)
            if not path:
                return
            q = self._read_quest_file(path)
            if q is None:
                return
            record = q.to_bytes()
        else:
            items = []
            for i, b in enumerate(self.backups.list_quests()):
                items.append({"key": i, "name": b.get("name", "?"),
                              "sub": f"{b.get('time', '')}  ·  was in {pack_label(b.get('pack', '?'))}, "
                                     f"slot {b.get('slot', '?')}", "_p": b["path"]})
            if not items:
                messagebox.showinfo(APP_TITLE, "No replaced quest has been backed up yet.", parent=self)
                return
            i = picker._run(self, title="Choose a backed-up quest", entries=items, tile=(440, 54),
                            icon_size=0, columns=2)
            if i is None:
                return
            record = Path(items[i]["_p"]).read_bytes()
        if src.get(key) is not None and not messagebox.askyesno(
                APP_TITLE, "Replace the quest in this slot? A backup of it is made when you save.", parent=self):
            return
        try:
            src.restore_quest(key, record)
        except (PackError, QuestFormatError) as exc:
            messagebox.showerror(APP_TITLE, str(exc), parent=self)
            return
        ql.refresh(select=key)
        self.pages["ingame"].build_status()
        self.mark_unsaved()
        self.set_status(f"Quest placed in {slot_label(key)} - save to write it to the game.")

    def clear_slot(self):
        src = self.sources["packs"]
        ql = self._ingame_list()
        key = ql.selected()
        q = src.get(key) if (src and key) else None
        if q is None:
            return
        if not messagebox.askyesno(APP_TITLE, f"Clear '{q.get_text('name', 0)}' from {slot_label(key)}?\n\n"
                                   "It disappears from the game when you save. A copy is kept in Backups "
                                   "and you can put it back from there.", parent=self):
            return
        src.delete(key)
        ql.refresh(select=key)
        self.pages["ingame"].build_status()
        self.mark_unsaved()
        self.set_status("Slot cleared - save to apply.")

    def to_library(self):
        _ql, _src, _key, q = self._sel_quest()
        lib = self.sources["library"]
        if q is None or lib is None:
            return
        key = lib.add(q)
        self.pages["library"].build_status()
        self.set_status(f"'{q.get_text('name', 0)}' copied to your quest library (a separate copy: the original "
                        "is not changed).")
        if messagebox.askyesno(APP_TITLE, f"'{q.get_text('name', 0)}' is now in your quest library, as a separate "
                               "copy: changing it never touches the original.\n\nOpen the copy now?", parent=self):
            self.show_page("library")
            ql = self.pages["library"].list
            ql.refresh(select=key)
            self.edit_kind = "library"
            self.open_editor("library", key)

    def export_quest(self):
        _ql, _src, _key, q = self._sel_quest()
        if q is None:
            return
        name = "".join(ch for ch in q.get_text("name", 0) if ch.isalnum() or ch in " _-").strip() or "quest"
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".mh3uq", filetypes=QUEST_TYPES,
                                            initialfile=f"{name}.mh3uq")
        if path:
            Path(path).write_bytes(q.to_bytes().rstrip(b"\0"))
            self.set_status(f"Exported to {path}")

    def _read_quest_file(self, path):
        try:
            return Quest(Path(path).read_bytes())
        except (OSError, QuestFormatError) as exc:
            messagebox.showerror(APP_TITLE, f"This is not an MH3U quest file.\n\n{exc}", parent=self)
            return None

    def import_to_library(self):
        lib = self.sources["library"]
        if lib is None:
            return
        paths = filedialog.askopenfilenames(parent=self, filetypes=QUEST_TYPES)
        added = 0
        for p in paths:
            try:
                lib.import_file(Path(p))
                added += 1
            except (OSError, QuestFormatError):
                messagebox.showwarning(APP_TITLE, f"Skipped (not a quest file):\n{p}", parent=self)
        if added:
            self.pages["library"].build_status()
            self.pages["library"].list.refresh()
            self.set_status(f"{added} quest(s) imported into your library.")

    def new_library_quest(self):
        lib = self.sources["library"]
        tpl = self.pick_template("New library quest: choose a quest to copy")
        if tpl is None:
            return
        name = simpledialog.askstring("New quest", "Name of the new quest:", initialvalue="My Custom Quest", parent=self)
        if not name:
            return
        q = tpl.copy()
        q.set_text("name", name)
        key = lib.add(q, name)
        self.pages["library"].build_status()
        self.pages["library"].list.refresh(select=key)
        self.open_editor("library", key)

    def duplicate_library(self):
        lib = self.sources["library"]
        key = self.pages["library"].list.selected()
        q = lib.get(key) if key else None
        if q is None:
            return
        new = lib.add(q, q.get_text("name", 0) + " copy")
        self.pages["library"].build_status()
        self.pages["library"].list.refresh(select=new)

    def delete_library(self):
        lib = self.sources["library"]
        key = self.pages["library"].list.selected()
        if key and messagebox.askyesno(APP_TITLE, "Delete this quest from your library?\n(It is moved to "
                                       "library/_deleted.)", parent=self):
            lib.delete(key)
            self.pages["library"].build_status()
            self.pages["library"].list.refresh()

    def send_to_game(self):
        lib, packs = self.sources["library"], self.sources["packs"]
        key = self.pages["library"].list.selected()
        q = lib.get(key) if key else None
        if q is None:
            return
        if packs is None:
            messagebox.showinfo(APP_TITLE, "Your MH3U save was not found yet (In-game quests page).", parent=self)
            return
        entries = []
        for e in packs.entries():
            if e.group not in EVENT_PACKS:
                continue
            title = slot_label(e.key)
            if e.quest is None:
                entries.append({"key": e.key, "name": title, "sub": "Free slot", "cat": "Free slots",
                                "search": title + " free", "icon": (lambda: self.icons.blank(27))})
            else:
                entries.append({"key": e.key, "name": title, "sub": "Replace: " + e.quest.get_text("name", 0),
                                "cat": "Replace a quest", "search": title + " " + e.quest.get_text("name", 0),
                                "icon": (lambda q_=e.quest: self.icons.quest(q_, 27))})
        dest = picker._run(self, title="To game: choose an event slot", entries=entries, tile=(320, 48),
                           icon_size=27, columns=3, categories=["Free slots", "Replace a quest"],
                           note="The quest keeps its number if no other quest uses it. Nothing is written "
                                "until you save.")
        if dest is None:
            return
        if packs.get(dest) is not None and not messagebox.askyesno(
                APP_TITLE, "Replace the quest in that slot? A backup of it is made when you save.", parent=self):
            return
        try:
            packs.restore_quest(dest, q.to_bytes())
        except PackError as exc:
            messagebox.showerror(APP_TITLE, str(exc), parent=self)
            return
        self.pages["ingame"].build_status()
        self.pages["ingame"].event.refresh(select=dest)
        self.mark_unsaved()
        self.set_status(f"Quest placed in {slot_label(dest)} - save to write it to the game.")

    def revert_rom(self):
        src = self.sources["rom"]
        key = self.pages["rom"].list.selected()
        if src and key and messagebox.askyesno(APP_TITLE, "Undo your changes to this quest?", parent=self):
            src.revert(key)
            self.pages["rom"].list.refresh(select=key)

    def backup_now(self):
        src = self.sources["packs"]
        if src is None:
            return
        dest = self.backups.snapshot([src.folder / n for n in src.packs], reason="made by hand")
        self.pages["ingame"].backups.fill()
        self.set_status(f"Full backup made: {dest}")

    # ------------------------------------------------------------------ save
    def dirty_sources(self):
        return [s for s in self.sources.values() if s is not None and s.dirty()]

    def save(self) -> bool:
        dirty = self.dirty_sources()
        if not dirty:
            self.set_status("Nothing to save.")
            return True
        if any(s.kind == "packs" for s in dirty) and not self._warned:
            if not messagebox.askokcancel(APP_TITLE, "Close Citra (or the game) before saving, otherwise it "
                                          "can overwrite your changes when it exits.\n\nA full backup of your "
                                          "save's quest files, and a copy of every quest you replace, are made "
                                          "first (In-game quests > Backups).\n\nSave now?", parent=self):
                return False
            self._warned = True
        done = []
        for src in dirty:
            try:
                written = src.save()
                if src.kind == "rom":
                    written = src.export_mod(ROM_OUTPUT)
            except (PackError, OSError, ValueError) as exc:
                messagebox.showerror(APP_TITLE, str(exc), parent=self)
                return False
            done.append((src.kind, written))
        self.export_supply()
        self.title(APP_TITLE)
        key, kind = self.editor.key, self.edit_kind
        editing = self.editor.winfo_ismapped()
        self.reload_lists(show=False)
        if editing and kind and self.sources[kind] and self.sources[kind].get(key) is not None:
            self.open_editor(kind, key)
        msg = [{"packs": "quests written to your save (backup made)", "library": "library saved"}.get(
            k, f"base-game mod written to {ROM_OUTPUT}") for k, _w in done]
        self.set_status("Saved: " + "; ".join(msg) + ".")
        return True

    # ----------------------------------------------------------------- paths
    def find_packs(self):
        found = find_emulator_pack_dirs()
        if not found:
            messagebox.showinfo(APP_TITLE, "No Citra save of MH3U was found.\n\nStart the game once in Citra "
                                "(it creates the files), close it, and try again - or choose the folder "
                                "yourself.", parent=self)
            return
        if self._set_packs(found[0]):
            self.reload_lists()

    def choose_packs(self):
        start = os.environ.get("APPDATA") or str(Path.home())
        folder = filedialog.askdirectory(parent=self, title="Choose your Citra folder (or the folder with "
                                         "quest1 ... quest4)", initialdir=start)
        if folder and self._set_packs(folder):
            self.reload_lists()

    def reload_packs(self):
        src = self.sources["packs"]
        if src and src.dirty() and not messagebox.askyesno(APP_TITLE, "Discard your unsaved changes and "
                                                           "reload the files?", parent=self):
            return
        if src:
            src.reload()
        self.title(APP_TITLE)
        self.reload_lists()

    def choose_romfs(self):
        folder = filedialog.askdirectory(parent=self, title="Choose the extracted 'romfs' folder of MH3U")
        if not folder:
            return
        from .monsterpack import detect_region
        found = detect_region(folder)
        if found and found != G.REGION:
            if not messagebox.askyesno(
                    APP_TITLE, f"This extracted game is the {G.region_name(found)} version, but the editor is set "
                    f"to the {G.region_name()} version.\n\nSwitch the editor to the {G.region_name(found)} "
                    "version?", parent=self):
                return
            if not self.switch_region(found):
                return
        try:
            self.sources["rom"] = RomSource(folder)
        except (PackError, OSError, ValueError) as exc:
            messagebox.showerror(APP_TITLE, f"This does not look like the game's romfs folder.\n\n{exc}", parent=self)
            return
        self.settings.set(self.setting_key("romfs"), folder)
        self._base_cache = None
        if self.sources["packs"]:
            self.sources["packs"].reserved = set(self.sources["rom"].originals)
        self.reload_lists()
        if not self.icons.has_art and messagebox.askyesno(
                APP_TITLE, "The monster, item and map pictures are missing. Build them from this game now?\n\n"
                "The editor reads them from your own copy of the game, on your computer (a few seconds, "
                "needs the Pillow package).", parent=self):
            self.build_pictures()

    def build_pictures(self):
        """Read the icons and map pictures from the player's own extracted game (see artbuild.py)."""
        from . import artbuild
        romfs = self.romfs_dir()
        if not romfs or not Path(romfs).is_dir():
            messagebox.showinfo(APP_TITLE, "Choose the extracted game's romfs folder first "
                                "(Settings > Choose the romfs folder...).", parent=self)
            return False
        if not artbuild.pillow_available():
            messagebox.showinfo(APP_TITLE, "The Pillow package is needed to read the game's pictures.\n\n"
                                "Open a command prompt and run:\n    py -m pip install pillow\n\nThen try again.",
                                parent=self)
            return False
        code = artbuild.default_code_bin(romfs)
        if code is None and messagebox.askyesno(
                APP_TITLE, "The item icons need the game's exefs/code.bin (it was not found next to the "
                "romfs folder).\n\nChoose it now? If you answer No, the editor shows no item icons.", parent=self):
            f = filedialog.askopenfilename(parent=self, title="Choose exefs/code.bin of MH3U",
                                           filetypes=[("code.bin", "code.bin"), ("All files", "*.*")])
            code = Path(f) if f else None
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            res = artbuild.build(romfs, ROOT_DIR, code=code)
        except (artbuild.ArtError, OSError, ValueError, struct.error) as exc:
            self.configure(cursor="")
            messagebox.showerror(APP_TITLE, f"The pictures could not be built:\n\n{exc}", parent=self)
            return False
        self.configure(cursor="")
        self.icons.reload()
        self.apply_theme(self.settings.get("theme", theme.DEFAULT_THEME))
        self.set_status(f"Pictures built from your game: {res['monsters']} monsters, {res['items']} items, "
                        f"{res['maps']} maps.")
        return True

    def reload_lists(self, show=True):
        self.pages["ingame"].build_status()
        self.pages["library"].build_status()
        self.pages["rom"].build_status()
        for ql in self.all_lists():
            ql.build_actions()
            ql.refresh()
        self.pages["ingame"].backups.fill()
        if show and not self.editor.winfo_ismapped():
            self.show_page(self.page)

    # ------------------------------------------------------- custom supply boxes
    def supply_in_use(self) -> set:
        """Supply box numbers used by the quests you have (including unsaved edits)."""
        used = set()
        for kind in ("packs", "library"):
            src = self.sources.get(kind)
            if src is None:
                continue
            try:
                for e in src.entries():
                    if e.quest is not None:
                        used.add(e.quest.get("item_set_no"))
            except (OSError, ValueError):
                pass
        return used

    def supply_users(self, no) -> list[str]:
        """Names of your quests (event packs and library) that open supply box ``no``."""
        out = []
        for kind in ("packs", "library"):
            src = self.sources.get(kind)
            if src is None:
                continue
            try:
                for e in src.entries():
                    if e.quest is not None and e.quest.get("item_set_no") == no:
                        out.append(e.quest.get_text("name", 0) or "(untitled)")
            except (OSError, ValueError):
                pass
        return out

    def citra_supply(self) -> tuple[list, dict]:
        """(Citra mod folders found, {number: [installed supply files]})."""
        dests = [d for d in find_emulator_mod_dirs()]
        return dests, supp.installed_files(dests)

    def remove_citra_supply(self, numbers) -> tuple[int, list]:
        """Delete the installed supply files of these numbers; returns (deleted, [errors])."""
        _dests, files = self.citra_supply()
        done, errors = 0, []
        for no in numbers:
            for f in files.get(no, []):
                try:
                    f.unlink()
                    done += 1
                except OSError as exc:
                    errors.append(f"{f}: {exc}")
        return done, errors

    def delete_box(self, no) -> tuple[int, list]:
        """Delete one of your boxes: the box itself, its file in Citra and in the output folder."""
        done, errors = self.remove_citra_supply([no])
        self.boxes.release(no)
        try:
            (SUPPLY_OUTPUT / "quest" / "support" / supp.file_name(no)).unlink(missing_ok=True)
        except OSError:
            pass
        return done, errors

    def open_boxes(self):
        from .editor import BoxManager
        BoxManager(self)
        if self.editor.winfo_ismapped():
            self.editor.reload_tabs()

    def export_supply(self) -> list:
        """Write the supply files of the custom boxes that quests use; returns the files."""
        if not self.boxes.numbers():
            return []
        folder = SUPPLY_OUTPUT / "quest" / "support"
        if folder.is_dir():
            for old in folder.glob("supp*.supp"):
                try:
                    old.unlink()
                except OSError:
                    pass
        try:
            return self.boxes.export(SUPPLY_OUTPUT, keep=self.supply_in_use())
        except (OSError, ValueError) as exc:
            messagebox.showerror(APP_TITLE, f"The custom supply files could not be written:\n{exc}", parent=self)
            return []

    def install_supply_mod(self):
        files = self.export_supply()
        if not files:
            messagebox.showinfo(APP_TITLE, "No quest uses a custom supply box yet.", parent=self)
            return
        dests = find_emulator_mod_dirs()
        if not dests:
            messagebox.showinfo(APP_TITLE, f"Citra's 'load' folder was not found. Copy\n{SUPPLY_OUTPUT}\ninto "
                                f"<Citra folder>/load/mods/{G.TITLE_ID}/romfs  (real 3DS with Luma: "
                                f"luma/titles/{G.TITLE_ID}/romfs)", parent=self)
            return
        if messagebox.askyesno(APP_TITLE, f"Copy {len(files)} supply file(s) into:\n{dests[0]}", parent=self):
            shutil.copytree(SUPPLY_OUTPUT, dests[0], dirs_exist_ok=True)
            self.set_status(f"Supply files installed in {dests[0]}")

    def install_rom_mod(self):
        if not ROM_OUTPUT.is_dir():
            messagebox.showinfo(APP_TITLE, "Edit and save a base-game quest first.", parent=self)
            return
        dests = find_emulator_mod_dirs()
        if not dests:
            messagebox.showinfo(APP_TITLE, f"Citra's 'load' folder was not found. Copy\n{ROM_OUTPUT}\ninto "
                                f"<Citra folder>/load/mods/{G.TITLE_ID}/romfs", parent=self)
            return
        if messagebox.askyesno(APP_TITLE, f"Copy the mod into:\n{dests[0]}", parent=self):
            shutil.copytree(ROM_OUTPUT, dests[0], dirs_exist_ok=True)
            self.set_status(f"Mod installed in {dests[0]}")

    # ----------------------------------------------------------- monster pack
    def monster_pack_dir(self) -> Path:
        return PACK_OUTPUT / f"MH3U_Monster_Pack_{G.REGION.upper()}"

    def installed_monster_pack(self):
        """(manifest, folder) of the pack installed in an emulator, or (None, None)."""
        for d in find_emulator_title_dirs():
            man = monsterpack.read_manifest(d)
            if man:
                return man, d
        return None, None

    def monster_pack(self):
        """(manifest, installed) used by the quest checks: the installed pack, else the built one.
        Cached; forget_monster_pack() after building, installing or removing."""
        if getattr(self, "_pack_state", None) is None:
            inst, _where = self.installed_monster_pack()
            self._pack_state = (inst, True) if inst else (monsterpack.read_manifest(self.monster_pack_dir()), False)
        return self._pack_state

    def forget_monster_pack(self):
        self._pack_state = None

    def build_monster_pack(self):
        romfs = self.romfs_dir()
        if not romfs or not Path(romfs).is_dir():
            messagebox.showinfo(APP_TITLE, "Choose your extracted game first (Settings > Choose the romfs "
                                "folder). exefs/code.bin must be next to the romfs folder.", parent=self)
            return
        page = self.pages["pack"]
        page.build_btn.configure(state="disabled")
        self.configure(cursor="watch")
        result = {}
        msgs = []

        def work():
            try:
                result["man"] = monsterpack.build(romfs, self.monster_pack_dir(), log=msgs.append)
            except (monsterpack.PackError, OSError, ValueError, struct.error, KeyError) as exc:
                result["err"] = exc

        th = threading.Thread(target=work, daemon=True)
        th.start()

        def poll():
            if msgs:
                page.progress.configure(text=msgs[-1])
            if th.is_alive():
                self.after(150, poll)
                return
            self.configure(cursor="")
            if "err" in result:
                messagebox.showerror(APP_TITLE, f"The pack could not be built:\n\n{result['err']}", parent=self)
            else:
                man = result["man"]
                if man.get("region") and man["region"] != G.REGION:
                    messagebox.showwarning(APP_TITLE, f"Your extracted game is the {G.region_name(man['region'])} "
                                           f"version, but the editor is set to {G.region_name()}.", parent=self)
                self.set_status(f"Monster pack built: {len(man['added'])} combinations, fingerprint "
                                f"{man['fingerprint']}.")
            self.forget_monster_pack()
            page.refresh()

        poll()

    def install_monster_pack(self):
        dests = find_emulator_title_dirs()
        if not dests:
            messagebox.showinfo(APP_TITLE, "Citra's 'load' folder was not found. Copy the content of\n"
                                f"{self.monster_pack_dir()}\ninto <Citra folder>/load/mods/{G.TITLE_ID}/  "
                                f"(real 3DS with Luma: luma/titles/{G.TITLE_ID}/)", parent=self)
            return
        if not messagebox.askyesno(APP_TITLE, f"Install the monster pack (ROM hack) into:\n{dests[0]}\n\n"
                                   "Close Citra first. Untested combinations may crash the game: back up your "
                                   "save. Continue?", parent=self):
            return
        try:
            n = len(monsterpack.install(self.monster_pack_dir(), dests[0]))
        except (monsterpack.PackError, OSError) as exc:
            messagebox.showerror(APP_TITLE, str(exc), parent=self)
            return
        self.forget_monster_pack()
        self.set_status(f"Monster pack installed ({n} files). Restart the game in Citra to load it.")
        self.pages["pack"].refresh()

    def remove_monster_pack(self):
        _man, where = self.installed_monster_pack()
        if where is None:
            return
        if not messagebox.askyesno(APP_TITLE, f"Remove the monster pack from\n{where}?\n\nQuests that rely on it "
                                   "will then miss their monster.", parent=self):
            return
        try:
            n = monsterpack.uninstall(where)
        except OSError as exc:
            messagebox.showerror(APP_TITLE, str(exc), parent=self)
            return
        self.forget_monster_pack()
        self.set_status(f"Monster pack removed ({n} files).")
        self.pages["pack"].refresh()

    # ------------------------------------------------------------- dialogs
    def first_run(self):
        if self.settings.get("setup_done"):
            return
        SetupDialog(self)

    def open_settings(self):
        SettingsDialog(self)

    def open_backups(self):
        if self.editor.winfo_ismapped() and not self.editor.leave():
            return
        self.show_page("ingame")
        ig = self.pages["ingame"]
        ig.nb.select(ig.backups)
        ig.backups.fill()

    def apply_language(self, code):
        """Switch English / French: the window is rebuilt with the new texts."""
        self.settings.set("language", code)
        i18n.set_language(code)
        G.set_names_language(code)
        self.apply_theme(self.settings.get("theme", theme.DEFAULT_THEME))

    def apply_theme(self, key):
        self.settings.set("theme", key)
        theme.apply(self, key)
        self.icons.clear()
        page, kind, key_ = self.page, self.edit_kind, self.editor.key
        editing = self.editor.winfo_ismapped()
        snap = self.editor.snapshot
        self.build_ui()
        if editing and kind and key_ is not None:
            self.open_editor(kind, key_, keep_snapshot=True)
            self.editor.snapshot = snap
        else:
            self.show_page(page)

    def on_close(self):
        if self.dirty_sources():
            ans = messagebox.askyesnocancel(APP_TITLE, "You have unsaved changes. Save them before closing?", parent=self)
            if ans is None or (ans and not self.save()):
                return
        self.destroy()


# =================================================================== dialogs
class Dialog(tk.Toplevel):
    def __init__(self, app, title):
        super().__init__(app)
        self.withdraw()
        self.app = app
        self.title(title)
        self.transient(app)
        self.configure(background=theme.color("bg"))
        self.bind("<Escape>", lambda _e: self.destroy())

    def finish(self):
        center_on(self, self.app)
        self.deiconify()
        make_modal(self)


def theme_choice(parent, var):
    """Clickable previews of the two themes."""
    box = ttk.Frame(parent)
    fam = theme.FONTS["body"].actual("family")
    serif = theme.FONTS["h3"].actual("family")
    for key, t in theme.THEMES.items():
        card = ttk.Frame(box, style="Box.TFrame", padding=10)
        card.pack(side="left", padx=(0, 12))
        sw = tk.Canvas(card, width=250, height=120, highlightthickness=1, highlightbackground=t["line"],
                       borderwidth=0, cursor="hand2")
        sw.pack()
        sw.create_rectangle(0, 0, 252, 24, fill=t["header"], outline="")
        sw.create_text(8, 12, text="MH3U Quest Editor", anchor="w", fill=t["header_ink"], font=(serif, 9, "bold"))
        sw.create_rectangle(0, 24, 252, 122, fill=t["bg"], outline="")
        sw.create_rectangle(8, 32, 242, 76, fill=t["card"], outline=t["line"])
        sw.create_text(16, 45, text="Colorful Beasts", anchor="w", fill=t["ink"], font=(serif, 10, "bold"))
        sw.create_text(16, 63, text="Deserted Island  ·  50 min", anchor="w", fill=t["muted"], font=(fam, 8))
        sw.create_text(234, 45, text="★★★", anchor="e", fill=t["gold"], font=(fam, 9))
        sw.create_text(8, 92, text="Health", anchor="w", fill=t["ink"], font=(fam, 8))
        sw.create_rectangle(50, 88, 140, 96, fill=t["bar_bg"], outline="")
        sw.create_rectangle(50, 88, 106, 96, fill=t["bar"], outline="")
        sw.create_rectangle(166, 84, 242, 108, fill=t["accent"], outline="")
        sw.create_text(204, 96, text="Save", fill=t["accent_ink"], font=(fam, 9, "bold"))
        sw.bind("<Button-1>", lambda _e, k=key: var.set(k))
        ttk.Radiobutton(card, text=t["name"] + ("  (default)" if key == theme.DEFAULT_THEME else ""),
                        value=key, variable=var, style="Card.TRadiobutton").pack(anchor="w", pady=(6, 0))
        ttk.Label(card, text=t.get("desc", ""), style="Card.Muted.TLabel").pack(anchor="w")
    return box


class SetupDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Welcome to the MH3U Quest Editor")
        f = ttk.Frame(self, padding=18)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Welcome, hunter!", style="Title.TLabel").pack(anchor="w")
        ttk.Label(f, wraplength=640, justify="left", text=(
            "This editor writes your quests straight into the game's event quest list. It works on the "
            "files Citra keeps for MH3U and finds them for you: there is no path to type.")).pack(anchor="w", pady=(4, 10))
        ttk.Label(f, text="1.  Your game", style="H3.TLabel").pack(anchor="w")
        vrow = ttk.Frame(f)
        vrow.pack(anchor="w", pady=(2, 2))
        ttk.Label(vrow, text="Version of your copy of MH3U:").pack(side="left")
        self.region = tk.StringVar(value=G.REGION)
        for r, inf in G.REGIONS.items():
            ttk.Radiobutton(vrow, text=f"{inf['name']}  ({inf['title_id']})", value=r, variable=self.region,
                            command=self._version).pack(side="left", padx=(8, 0))
        self.status = ttk.Label(f, text="", wraplength=640, justify="left")
        self.status.pack(anchor="w", pady=(2, 4))
        row = ttk.Frame(f)
        row.pack(anchor="w")
        ttk.Button(row, text="Find automatically", style="Accent.TButton", command=self._find).pack(side="left")
        ttk.Button(row, text="Choose the folder myself...", command=self._choose).pack(side="left", padx=6)
        ttk.Label(f, text="2.  Choose a theme (you can change it later in Settings)",
                  style="H3.TLabel").pack(anchor="w", pady=(14, 6))
        self.theme = tk.StringVar(value=app.settings.get("theme", theme.DEFAULT_THEME))
        theme_choice(f, self.theme).pack(anchor="w")
        ttk.Label(f, text="3.  Optional: extracted game files", style="H3.TLabel").pack(anchor="w", pady=(14, 2))
        ttk.Label(f, wraplength=640, justify="left", style="Muted.TLabel", text=(
            "Needed to edit the game's own (non-event) quests, to copy them as templates. "
            "You can add it later in Settings.")).pack(anchor="w")
        ttk.Button(f, text="Choose the romfs folder...", command=app.choose_romfs).pack(anchor="w", pady=4)
        b = ttk.Frame(f)
        b.pack(fill="x", pady=(14, 0))
        ttk.Button(b, text="Start editing", style="Accent.TButton", command=self._done).pack(side="right")
        self._update()
        self.finish()

    def _update(self):
        src = self.app.sources["packs"]
        if src:
            self.status.configure(text=f"Found: {short_path(src.folder, 90)}", style="Ok.TLabel")
        else:
            self.status.configure(text="Not found yet. Start MH3U once in Citra, close it, then press "
                                       "'Find automatically'. For a real 3DS, copy its extra data to your PC "
                                       "and choose that folder.", style="Warn.TLabel")

    def _version(self):
        if not self.app.switch_region(self.region.get()):
            self.region.set(G.REGION)
        self.lift()
        self._update()

    def _find(self):
        self.app.find_packs()
        self._update()

    def _choose(self):
        self.app.choose_packs()
        self._update()

    def _done(self):
        self.app.settings.set("setup_done", True)
        key = self.theme.get()
        self.destroy()
        if key != self.app.settings.get("theme", theme.DEFAULT_THEME):
            self.app.apply_theme(key)
        else:
            self.app.settings.set("theme", key)


class SettingsDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Settings")
        f = ttk.Frame(self, padding=18)
        f.pack(fill="both", expand=True)
        lrow = ttk.Frame(f)
        lrow.pack(anchor="w", pady=(0, 12))
        ttk.Label(lrow, text="Language / Langue", style="H3.TLabel").pack(side="left", padx=(0, 12))
        self.lang = tk.StringVar(value=i18n.LANG)
        for code, name in i18n.LANGUAGES.items():
            ttk.Radiobutton(lrow, text=name, value=code, variable=self.lang,
                            style="Seg.TRadiobutton").pack(side="left", padx=1)
        ttk.Label(f, text="Theme", style="H3.TLabel").pack(anchor="w")
        self.theme = tk.StringVar(value=app.settings.get("theme", theme.DEFAULT_THEME))
        theme_choice(f, self.theme).pack(anchor="w", pady=(4, 12))
        ttk.Label(f, text="Display", style="H3.TLabel").pack(anchor="w")
        self.tips = tk.BooleanVar(value=bool(app.settings.get("tooltips", True)))
        ttk.Checkbutton(f, text="Show explanations when the mouse is over an (i)", variable=self.tips).pack(anchor="w")
        row = ttk.Frame(f)
        row.pack(anchor="w")
        ttk.Checkbutton(row, text="Developer mode (internal numbers, hex values, Advanced tab)",
                        variable=app.dev_mode, command=app.toggle_dev).pack(side="left")
        info(row, H.tip("dev_mode")).pack(side="left", padx=4)
        ttk.Label(f, text="Your game", style="H3.TLabel").pack(anchor="w", pady=(12, 2))
        vrow = ttk.Frame(f)
        vrow.pack(anchor="w", pady=(0, 4))
        ttk.Label(vrow, text="Game version:").pack(side="left")
        self.region = tk.StringVar(value=G.REGION)
        for r, inf in G.REGIONS.items():
            ttk.Radiobutton(vrow, text=f"{inf['name']}  ({inf['title_id']})", value=r,
                            variable=self.region).pack(side="left", padx=(8, 0))
        packs = app.sources["packs"]
        ttk.Label(f, text="Quest files: " + (short_path(packs.folder, 90) if packs else "not found"),
                  style="Muted.TLabel").pack(anchor="w")
        r = ttk.Frame(f)
        r.pack(anchor="w", pady=(2, 6))
        ttk.Button(r, text="Find automatically", command=lambda: (self.destroy(), app.find_packs())).pack(side="left")
        ttk.Button(r, text="Choose...", command=lambda: (self.destroy(), app.choose_packs())).pack(side="left", padx=6)
        rom = app.romfs_dir()
        ttk.Label(f, text="Extracted game (optional): " + (short_path(rom, 80) if rom else "not set"),
                  style="Muted.TLabel").pack(anchor="w")
        ttk.Button(f, text="Choose the romfs folder...",
                   command=lambda: (self.destroy(), app.choose_romfs())).pack(anchor="w", pady=2)
        art = ("installed" if app.icons.has_art else "missing (the editor shows empty pictures)")
        ttk.Label(f, text="Monster, item and map pictures: " + art, style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        ttk.Button(f, text="Rebuild the pictures from my game...",
                   command=lambda: (self.destroy(), app.build_pictures())).pack(anchor="w", pady=2)
        ttk.Label(f, text="Backups", style="H3.TLabel").pack(anchor="w", pady=(12, 2))
        br = ttk.Frame(f)
        br.pack(anchor="w")
        from .backup import KEEP_FULL, KEEP_PER_QUEST
        self.keep_full = tk.IntVar(value=int(app.settings.get("keep_full", KEEP_FULL)))
        self.keep_q = tk.IntVar(value=int(app.settings.get("keep_per_quest", KEEP_PER_QUEST)))
        ttk.Label(br, text="Full backups to keep").pack(side="left")
        ttk.Spinbox(br, from_=3, to=200, width=5, textvariable=self.keep_full).pack(side="left", padx=(4, 14))
        ttk.Label(br, text="Copies kept per quest").pack(side="left")
        ttk.Spinbox(br, from_=2, to=100, width=5, textvariable=self.keep_q).pack(side="left", padx=4)
        ttk.Label(f, style="Muted.TLabel", wraplength=640, justify="left", text=(
            "Older backups are deleted automatically. Never deleted: your original files, the very first full "
            "backup and the first copy of every quest.")).pack(anchor="w")
        ttk.Label(f, text=f"Library and backups are kept next to the program:\n{short_path(APP_DIR, 90)}",
                  style="Muted.TLabel").pack(anchor="w", pady=(10, 0))
        b = ttk.Frame(f)
        b.pack(fill="x", pady=(14, 0))
        ttk.Button(b, text="OK", style="Accent.TButton", command=self._ok).pack(side="right")
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right", padx=6)
        self.finish()

    def _ok(self):
        app = self.app
        app.settings.set("tooltips", bool(self.tips.get()))
        Tooltip.enabled = bool(self.tips.get())
        try:
            app.settings.set("keep_full", max(3, int(self.keep_full.get())))
            app.settings.set("keep_per_quest", max(2, int(self.keep_q.get())))
        except (tk.TclError, ValueError):
            pass
        app.backups.keep_full = int(app.settings.get("keep_full", app.backups.keep_full))
        app.backups.keep_per_quest = int(app.settings.get("keep_per_quest", app.backups.keep_per_quest))
        key = self.theme.get()
        region = self.region.get()
        lang = self.lang.get()
        self.destroy()
        if lang != i18n.LANG:
            app.apply_language(lang)
        if key != app.settings.get("theme", theme.DEFAULT_THEME):
            app.apply_theme(key)
        if region != G.REGION:
            app.switch_region(region)


def own_taskbar_identity():
    """Windows groups the taskbar button of a Python program under python.exe, with Python's icon.
    Giving the program its own identity makes the taskbar show this editor's icon."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MH3U.CustomQuestEditor")
    except Exception:
        pass


def run():
    own_taskbar_identity()
    install_selectable_labels()
    app = App()
    enable_tree_copy(app)
    app.mainloop()
