"""Search-and-pick dialogs with icons (monsters, items, maps, supply sets)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import gamedata as G
from . import theme
from .widgets import SearchBox, center_on, make_modal

SMALL_MONSTERS = {
    "Aptonoth", "Epioth", "Kelbi", "Popo", "Rhenoplos", "Slagtoth", "Slagtoth (Red)", "Anteka",
    "Bullfango", "Gargwa", "Altaroth", "Bnahabra", "Bnahabra (Blue)", "Bnahabra (Red)",
    "Bnahabra (Green/Brown)", "Jaggi", "Jaggia", "Baggi", "Wroggi", "Ludroth", "Uroktor", "Delex",
    "Giggi", "Giggi Egg", "Felyne", "Melynx", "Fish",
}


def monster_category(name: str) -> str:
    if name.startswith("Boulder"):
        return "Other"
    return "Small" if name in SMALL_MONSTERS else "Large"


def _hidden_item(name: str) -> bool:
    return (not name or name.startswith("(None)") or "DUMMY" in name or "(dup" in name
            or name.startswith("item #"))


class Picker(tk.Toplevel):
    """Modal grid of tiles: icon + name, a search box and category buttons.

    ``entries``: list of dicts with key, name, (sub), (cat), icon (callable
    returning a PhotoImage). Returns the chosen key in ``self.result``.
    """

    def __init__(self, parent, title, entries, *, tile=(150, 64), icon_size=48,
                 categories=None, initial=None, note=None, columns=None, dev=False):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.transient(parent.winfo_toplevel())
        self.configure(background=theme.color("bg"))
        self.entries = entries
        self.shown: list[dict] = []
        self.result = None
        self.tw, self.th = tile
        self.icon_size = icon_size
        self.sel = 0
        self.dev = dev
        self._icons = []

        top = ttk.Frame(self, padding=(12, 10, 12, 4))
        top.pack(fill="x")
        ttk.Label(top, text=title, style="H2.TLabel").pack(side="left")
        self.count = ttk.Label(top, text="", style="Muted.TLabel")
        self.count.pack(side="right")
        if note:
            ttk.Label(self, text=note, style="Muted.TLabel", wraplength=640,
                      padding=(12, 0, 12, 4)).pack(fill="x")
        bar = ttk.Frame(self, padding=(12, 4))
        bar.pack(fill="x")
        self.query = tk.StringVar()
        sb_ = SearchBox(bar, self.query, width=36)
        sb_.pack(side="left", fill="x", expand=True)
        ent = sb_.entry
        self.cat = tk.StringVar(value="All")
        if categories:
            seg = ttk.Frame(bar)
            seg.pack(side="left", padx=(10, 0))
            for c in ["All"] + list(categories):
                ttk.Radiobutton(seg, text=c, value=c, variable=self.cat, style="Seg.TRadiobutton",
                                command=self._fill).pack(side="left", padx=1)
        body = ttk.Frame(self, padding=(12, 4, 12, 4))
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body, width=(columns or 4) * self.tw + 4, height=min(5, 99) * self.th)
        theme.style_canvas(self.canvas, "panel")
        sb = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        btn = ttk.Frame(self, padding=(12, 6, 12, 12))
        btn.pack(fill="x")
        self.hint = ttk.Label(btn, text="Double-click or press Enter to choose", style="Muted.TLabel")
        self.hint.pack(side="left")
        ttk.Button(btn, text="Choose", style="Accent.TButton", command=self._ok).pack(side="right")
        ttk.Button(btn, text="Cancel", command=self.destroy).pack(side="right", padx=6)

        self.query.trace_add("write", lambda *_: self._fill())
        self.canvas.bind("<Configure>", lambda _e: self._layout())
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<Double-Button-1>", lambda e: (self._click(e), self._ok()))
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units"))
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-3, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(3, "units"))
        for seq, d in (("<Left>", -1), ("<Right>", 1)):
            self.bind(seq, lambda _e, d=d: self._move(d))
        self.bind("<Up>", lambda _e: self._move(-self._cols()))
        self.bind("<Down>", lambda _e: self._move(self._cols()))
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.canvas.configure(yscrollincrement=self.th // 2)
        self._fill(initial)
        center_on(self, parent.winfo_toplevel())
        self.deiconify()
        ent.focus_set()
        make_modal(self)

    def _cols(self):
        return max(1, (self.canvas.winfo_width() - 4) // self.tw)

    def _fill(self, initial=None):
        q = self.query.get().strip().lower()
        cat = self.cat.get()
        self.shown = [e for e in self.entries
                      if (cat == "All" or e.get("cat") == cat)
                      and (not q or q in e.get("search", e["name"]).lower())]
        self.sel = 0
        if initial is not None:
            for i, e in enumerate(self.shown):
                if e["key"] == initial:
                    self.sel = i
        self.count.configure(text=f"{len(self.shown)} shown")
        self._layout()

    def _layout(self):
        c = theme.current()
        cv = self.canvas
        cv.delete("all")
        self._icons = []
        cols = self._cols()
        for i, e in enumerate(self.shown):
            x, y = (i % cols) * self.tw + 2, (i // cols) * self.th + 2
            tag = f"t{i}"
            sel = i == self.sel
            cv.create_rectangle(x, y, x + self.tw - 4, y + self.th - 4, tags=(tag, "tile"),
                                fill=c["select"] if sel else c["card"],
                                outline=c["accent"] if sel else c["line"])
            img = e["icon"]() if e.get("icon") else None
            tx = x + 8
            if img is not None:
                self._icons.append(img)
                cv.create_image(x + 6, y + (self.th - 4) // 2, image=img, anchor="w", tags=(tag,))
                tx = x + 12 + self.icon_size
            name = e["name"]
            cv.create_text(tx, y + (self.th - 4) // 2 - (7 if e.get("sub") else 0), text=name,
                           anchor="w", width=self.tw - (tx - x) - 6, tags=(tag,),
                           fill=c["select_ink"] if sel else c["ink"], font=theme.FONTS["small"])
            if e.get("sub"):
                cv.create_text(tx, y + (self.th - 4) // 2 + 10, text=e["sub"], anchor="w",
                               width=self.tw - (tx - x) - 6, tags=(tag,), fill=c["muted"],
                               font=theme.FONTS["small"])
        rows = (len(self.shown) + cols - 1) // cols
        cv.configure(scrollregion=(0, 0, cols * self.tw, rows * self.th + 4))
        self._see()

    def _see(self):
        if not self.shown:
            return
        cols = self._cols()
        rows = (len(self.shown) + cols - 1) // cols
        r = self.sel // cols
        top, bottom = self.canvas.yview()
        if rows:
            frac = r / rows
            if frac < top or (r + 1) / rows > bottom:
                self.canvas.yview_moveto(max(0, frac - (bottom - top) / 3))

    def _click(self, e):
        cv = self.canvas
        x, y = cv.canvasx(e.x), cv.canvasy(e.y)
        cols = self._cols()
        i = int(y // self.th) * cols + int(x // self.tw)
        if 0 <= int(x // self.tw) < cols and 0 <= i < len(self.shown):
            self.sel = i
            top = cv.yview()[0]
            self._layout()
            cv.yview_moveto(top)

    def _move(self, d):
        if self.shown:
            self.sel = max(0, min(len(self.shown) - 1, self.sel + d))
            self._layout()

    def _ok(self):
        if self.shown:
            self.result = self.shown[self.sel]["key"]
            self.destroy()


def _run(parent, **kw):
    dlg = Picker(parent, **kw)
    parent.wait_window(dlg)
    return dlg.result


def pick_monster(app, initial=None, title="Choose a monster", allow_none=False, small_first=False):
    icons, dev = app.icons, app.dev_mode.get()
    entries = []
    if allow_none:
        entries.append({"key": 0, "name": "(none)", "cat": "All", "search": "none"})
    for em, name in sorted(G.MONSTERS.items(), key=lambda kv: kv[1]):
        sub = f"em{em:03d}" if dev else ""
        entries.append({"key": em, "name": name, "sub": sub, "cat": monster_category(name),
                        "search": f"{name} em{em:03d}" if dev else name,
                        "icon": (lambda em=em: icons.monster(em, 54))})
    return _run(app, title=title, entries=entries, tile=(190, 64), icon_size=54,
                categories=["Large", "Small", "Other"], initial=initial, columns=4, dev=dev)


def pick_item(app, initial=None, title="Choose an item"):
    icons, dev = app.icons, app.dev_mode.get()
    entries = []
    for iid, name in enumerate(G.ITEMS):
        if _hidden_item(name) and not dev:
            continue
        entries.append({"key": iid, "name": name, "sub": f"#{iid}" if dev else "",
                        "search": f"{name} #{iid}" if dev else name,
                        "icon": (lambda iid=iid: icons.item(iid, 2))})
    return _run(app, title=title, entries=entries, tile=(190, 52), icon_size=44,
                initial=initial, columns=4, dev=dev)


def pick_map(app, initial=None):
    icons = app.icons
    entries = [{"key": m, "name": n, "sub": f"map {m}" if app.dev_mode.get() else "",
                "icon": (lambda m=m: icons.map(m, 64))}
               for m, n in sorted(G.MAP_NAMES.items())]
    return _run(app, title="Choose the map", entries=entries, tile=(230, 76), icon_size=64,
                initial=initial, columns=3,
                note="Pick a map where your monsters have spawn data; the editor warns you otherwise.")


def pick_supply(app, initial=None):
    icons, dev = app.icons, app.dev_mode.get()
    entries = []

    def entry(no, items, name, cat):
        merged = {}
        for iid, qty in items:
            merged[iid] = merged.get(iid, 0) + qty
        names = [f"{G.item_name(i)} ×{q}" for i, q in merged.items()]
        first = next(iter(merged), None)
        if name is None:
            name = f"Set {no}" if dev or not merged else ", ".join(G.item_name(i) for i in list(merged)[:2])
        return {"key": no, "name": name, "cat": cat,
                "sub": ", ".join(names[:5]) + (" ..." if len(names) > 5 else ""),
                "search": f"{name} set {no} " + " ".join(names),
                "icon": (lambda i=first: icons.item(i, 2) if i is not None else None)}
    mine = app.boxes.numbers()
    for no in mine:
        entries.append(entry(no, app.boxes.items(no), app.boxes.name(no) + (f"  (set {no})" if dev else ""), "My boxes"))
    for no, items in sorted(G.SUPP_SETS.items()):
        if no in mine:
            continue
        entries.append(entry(no, items, None, "Game boxes"))
    return _run(app, title="Choose the supply crate", entries=entries, tile=(330, 64), icon_size=44,
                initial=initial, columns=2, categories=["My boxes", "Game boxes"] if mine else None,
                note="The game's boxes are fixed lists of items. Your own boxes (made in the Supply Box tab) "
                     "come first. Search for an item to find the boxes that contain it.")


def pick_small_species(app, allowed, title="Choose a small monster", initial=None, note=None):
    """Small monsters that the game's quests use on the quest's map. ``allowed``: species -> number
    of game quests on that map that use it."""
    icons, dev = app.icons, app.dev_mode.get()
    entries = []
    for em, n in sorted(allowed.items(), key=lambda kv: G.mon_name(kv[0])):
        entries.append({"key": em, "name": G.mon_name(em),
                        "sub": f"used in {n} game quest{'s' if n != 1 else ''} here" + (f" · em{em:03d}" if dev else ""),
                        "cat": "All", "search": f"{G.mon_name(em)} em{em:03d}" if dev else G.mon_name(em),
                        "icon": (lambda em=em: icons.monster(em, 54))})
    return _run(app, title=title, entries=entries, tile=(230, 64), icon_size=54, columns=3,
                initial=initial, dev=dev, note=note)
