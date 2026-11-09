"""Search-and-pick dialogs with icons (monsters, items, maps, supply sets).

The monster and item pickers are browsers: a side list of families (monster classes, item
families, or difficulty tiers), a search box that looks through everything, and a grid of tiles
with a heading for each family. Changing the selection only restyles two tiles, so nothing is
redrawn while you move around.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import catalog as C
from . import gamedata as G
from . import theme
from .i18n import _
from .widgets import SearchBox, center_on, make_modal

ALL = "All"
HEAD_H = 30


def monster_category(em: int) -> str:
    cls = C.MONSTER_CLASS.get(em, "Other")
    return cls if cls in ("Small monsters", "Other") else "Large"


def _hidden_item(name: str) -> bool:
    return (not name or name.startswith("(None)") or name.startswith("(Rien)") or "DUMMY" in name
            or "(dup" in name or name.startswith("item #"))


class Picker(tk.Toplevel):
    """Modal browser of tiles: icon + name (+ a second line), a search box and a side list of groups.

    ``entries``: dicts with key, name, (sub), (search), icon (callable returning a PhotoImage) and,
    for each view in ``views``, the group name under that view's key. ``views``: list of
    (label, entry key holding the group, ordered group names); one view = no view switch.
    Returns the chosen key in ``self.result``.
    """

    def __init__(self, parent, title, entries, *, tile=(150, 64), icon_size=48, views=None,
                 initial=None, note=None, columns=None, dev=False, side_width=190, categories=None):
        super().__init__(parent)
        if categories and not views:               # older callers: one flat list of categories
            views = [("Category", "cat", tuple(categories))]
        self.withdraw()
        self.title(title)
        self.transient(parent.winfo_toplevel())
        self.configure(background=theme.color("bg"))
        self.entries = entries
        self.views = views or []
        self.shown: list[dict] = []
        self.rects: list[tuple[int, int]] = []
        self.result = None
        self.tw, self.th = tile
        self.icon_size = icon_size
        self.sel = 0
        self.dev = dev
        self._icons = []
        self._cols_drawn = 0

        top = ttk.Frame(self, padding=(14, 12, 14, 4))
        top.pack(fill="x")
        ttk.Label(top, text=title, style="H2.TLabel").pack(side="left")
        self.count = ttk.Label(top, text="", style="Muted.TLabel")
        self.count.pack(side="right")
        if note:
            ttk.Label(self, text=note, style="Muted.TLabel", wraplength=760,
                      padding=(14, 0, 14, 4)).pack(fill="x")
        bar = ttk.Frame(self, padding=(14, 4))
        bar.pack(fill="x")
        self.query = tk.StringVar()
        sb_ = SearchBox(bar, self.query, width=40)
        sb_.pack(side="left", fill="x", expand=True)
        ent = sb_.entry
        self.view = tk.IntVar(value=0)
        if len(self.views) > 1:
            seg = ttk.Frame(bar)
            seg.pack(side="right", padx=(10, 0))
            ttk.Label(seg, text="Sort:", style="Muted.TLabel").pack(side="left", padx=(0, 4))
            for i, (label, _k, _g) in enumerate(self.views):
                ttk.Radiobutton(seg, text=label, value=i, variable=self.view, style="Seg.TRadiobutton",
                                command=self._new_view).pack(side="left", padx=1)

        body = ttk.Frame(self, padding=(14, 4, 14, 4))
        body.pack(fill="both", expand=True)
        self.group = tk.StringVar(value=ALL)
        self.side = None
        if self.views:
            self.side = ttk.Frame(body, width=side_width)
            self.side.pack(side="left", fill="y", padx=(0, 10))
        self.canvas = tk.Canvas(body, width=(columns or 4) * self.tw + 4, height=6 * self.th)
        theme.style_canvas(self.canvas, "panel")
        sb = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        btn = ttk.Frame(self, padding=(14, 6, 14, 12))
        btn.pack(fill="x")
        self.hint = ttk.Label(btn, text="Double-click or press Enter to choose", style="Muted.TLabel")
        self.hint.pack(side="left")
        ttk.Button(btn, text="Choose", style="Accent.TButton", command=self._ok).pack(side="right")
        ttk.Button(btn, text="Cancel", command=self.destroy).pack(side="right", padx=6)

        self.query.trace_add("write", lambda *_: self._fill())
        self.canvas.bind("<Configure>", self._resized)
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
        self._initial = initial
        self._build_side()
        if self.side is not None:                  # tall enough for the whole side list
            self.side.update_idletasks()
            self.canvas.configure(height=max(int(self.canvas.cget("height")), self.side.winfo_reqheight()))
        self._fill(initial)
        center_on(self, parent.winfo_toplevel())
        self.deiconify()
        ent.focus_set()
        make_modal(self)

    # ------------------------------------------------------------- groups
    def _view(self):
        return self.views[self.view.get()] if self.views else None

    def _group_of(self, e):
        v = self._view()
        return e.get(v[1], "") if v else ""

    def _build_side(self):
        if self.side is None:
            return
        for w in self.side.winfo_children():
            w.destroy()
        _label, key, groups = self._view()
        counts = {}
        for e in self.entries:
            counts[e.get(key, "")] = counts.get(e.get(key, ""), 0) + 1
        ttk.Radiobutton(self.side, text=f"{_('All')}  ({len(self.entries)})", value=ALL, variable=self.group,
                        style="Seg.TRadiobutton", command=self._fill).pack(fill="x", pady=(0, 4))
        for g in groups:
            if counts.get(g):
                ttk.Radiobutton(self.side, text=f"{_(g)}  ({counts[g]})", value=g, variable=self.group,
                                style="Seg.TRadiobutton", command=self._fill).pack(fill="x", pady=1)

    def _new_view(self):
        self.group.set(ALL)
        self._build_side()
        key = self.shown[self.sel]["key"] if self.shown else None
        self._fill(key)

    # ------------------------------------------------------------- content
    def _cols(self):
        return max(1, (self.canvas.winfo_width() - 4) // self.tw)

    def _fill(self, initial=None):
        if initial is None and self.shown and 0 <= self.sel < len(self.shown):
            initial = self.shown[self.sel]["key"]
        q = self.query.get().strip().lower()
        grp = self.group.get()
        v = self._view()
        shown = [e for e in self.entries
                 if (grp == ALL or self._group_of(e) == grp)
                 and (not q or q in e.get("search", e["name"]).lower())]
        if v:
            order = {g: i for i, g in enumerate(v[2])}
            shown.sort(key=lambda e: (order.get(self._group_of(e), len(order)), e.get(v[1] + "_order", 0)))
        self.shown = shown
        self.sel = 0
        if initial is not None:
            for i, e in enumerate(self.shown):
                if e["key"] == initial:
                    self.sel = i
                    break
        self.count.configure(text=f"{len(self.shown)} shown")
        self._layout()

    def _resized(self, _e=None):
        if self._cols() != self._cols_drawn:
            self._layout()

    def _layout(self):
        c = theme.current()
        cv = self.canvas
        cv.delete("all")
        self._icons = []
        cols = self._cols()
        self._cols_drawn = cols
        self.rects = []
        heads = bool(self.views) and self.group.get() == ALL
        y, col, last = 2, 0, object()
        for i, e in enumerate(self.shown):
            g = self._group_of(e)
            if heads and g != last:
                if col:
                    y += self.th
                    col = 0
                cv.create_text(6, y + HEAD_H // 2 + 2, text=_(g) if g else "", anchor="w", fill=c["accent"],
                               font=theme.FONTS["h3"])
                cv.create_line(6, y + HEAD_H - 3, cols * self.tw - 4, y + HEAD_H - 3, fill=c["line"])
                y += HEAD_H
                last = g
            x = col * self.tw + 2
            self.rects.append((x, y))
            self._draw_tile(i, e, x, y, i == self.sel)
            col += 1
            if col >= cols:
                col = 0
                y += self.th
        height = y + (self.th if col else 0) + 4
        cv.configure(scrollregion=(0, 0, cols * self.tw, height))
        self._see()

    def _draw_tile(self, i, e, x, y, sel):
        c = theme.current()
        cv = self.canvas
        tag = f"t{i}"
        cv.create_rectangle(x, y, x + self.tw - 4, y + self.th - 4, tags=(tag, tag + "box"),
                            fill=c["select"] if sel else c["card"], outline=c["accent"] if sel else c["line"],
                            width=2 if sel else 1)
        img = e["icon"]() if e.get("icon") else None
        tx = x + 8
        if img is not None:
            self._icons.append(img)
            cv.create_image(x + 6, y + (self.th - 4) // 2, image=img, anchor="w", tags=(tag,))
            tx = x + 12 + self.icon_size
        cv.create_text(tx, y + (self.th - 4) // 2 - (7 if e.get("sub") else 0), text=e["name"],
                       anchor="w", width=self.tw - (tx - x) - 6, tags=(tag, tag + "ink"),
                       fill=c["select_ink"] if sel else c["ink"], font=theme.FONTS["small"])
        if e.get("sub"):
            cv.create_text(tx, y + (self.th - 4) // 2 + 10, text=e["sub"], anchor="w",
                           width=self.tw - (tx - x) - 6, tags=(tag,), fill=e.get("sub_color") or c["muted"],
                           font=theme.FONTS["small"])

    def _restyle(self, i, sel):
        c = theme.current()
        self.canvas.itemconfigure(f"t{i}box", fill=c["select"] if sel else c["card"],
                                  outline=c["accent"] if sel else c["line"], width=2 if sel else 1)
        self.canvas.itemconfigure(f"t{i}ink", fill=c["select_ink"] if sel else c["ink"])

    def _see(self):
        if not self.shown or not self.rects:
            return
        _x, y = self.rects[self.sel]
        top, bottom = self.canvas.yview()
        region = self.canvas.cget("scrollregion").split()
        total = float(region[3]) if len(region) == 4 else 1.0
        if total <= 0:
            return
        if y / total < top or (y + self.th) / total > bottom:
            self.canvas.yview_moveto(max(0.0, (y - HEAD_H) / total))

    def _select(self, i):
        if 0 <= i < len(self.shown) and i != self.sel:
            self._restyle(self.sel, False)
            self.sel = i
            self._restyle(i, True)
        self._see()

    def _click(self, e):
        cv = self.canvas
        x, y = cv.canvasx(e.x), cv.canvasy(e.y)
        for i, (tx, ty) in enumerate(self.rects):
            if tx <= x < tx + self.tw - 4 and ty <= y < ty + self.th - 4:
                self._select(i)
                return

    def _move(self, d):
        if self.shown:
            self._select(max(0, min(len(self.shown) - 1, self.sel + d)))

    def _ok(self):
        if self.shown:
            self.result = self.shown[self.sel]["key"]
            self.destroy()


def _run(parent, **kw):
    dlg = Picker(parent, **kw)
    parent.wait_window(dlg)
    return dlg.result


DIFFICULTY_GROUPS = tuple(t[2] for t in C.THREAT_TIERS) + ("Small monsters", "Other")


def pick_monster(app, initial=None, title="Choose a monster", allow_none=False, small_first=False):
    """Monsters by class (easiest first in each class) or by difficulty tier."""
    icons, dev = app.icons, app.dev_mode.get()
    entries = []
    if allow_none:
        entries.append({"key": 0, "name": _("(none)"), "type": "Other", "tier": "Other", "search": "none"})
    for em, name in G.MONSTERS.items():
        cls = C.MONSTER_CLASS.get(em, "Other")
        threat = C.MONSTER_THREAT.get(em, 0)
        stars = C.threat_text(em)
        sub = (stars + (f"  em{em:03d}" if dev else "")) if stars else (f"em{em:03d}" if dev else "")
        entries.append({"key": em, "name": name, "sub": sub,
                        "sub_color": theme.color("gold") if stars else None,
                        "type": cls, "type_order": (threat, name),
                        "tier": C.threat_tier(em) or cls, "tier_order": (threat, name),
                        "search": f"{name} {C.english_name(em)} {_(cls)}" + (f" em{em:03d}" if dev else ""),
                        "icon": (lambda em=em: icons.monster(em, 54))})
    small_groups = ("Small monsters",) if small_first else ()
    type_groups = small_groups + tuple(g for g in C.MONSTER_CLASSES if g not in small_groups)
    return _run(app, title=title, entries=entries, tile=(200, 64), icon_size=54,
                views=[("By type", "type", type_groups), ("By difficulty", "tier", DIFFICULTY_GROUPS)],
                initial=initial, columns=4, dev=dev,
                note="Stars: how hard players usually find the monster (an editorial guide, not a game value). "
                     "The quest's Health and Attack rows decide how strong it really is.")


def pick_item(app, initial=None, title="Choose an item"):
    """Items by family (as the game draws their icons), in the game's own order."""
    icons, dev = app.icons, app.dev_mode.get()
    index = icons.index
    entries = []
    for iid, name in enumerate(G.ITEMS):
        if _hidden_item(name) and not dev:
            continue
        fam = C.item_group(iid, index)
        entries.append({"key": iid, "name": name, "sub": f"#{iid}" if dev else "",
                        "family": fam, "family_order": iid,
                        "search": f"{name} {G.english_item(iid)} {_(fam)}" + (f" #{iid}" if dev else ""),
                        "icon": (lambda iid=iid: icons.item(iid, 2))})
    return _run(app, title=title, entries=entries, tile=(200, 52), icon_size=44,
                views=[("By family", "family", C.ITEM_GROUPS)], initial=initial, columns=4, dev=dev)


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
        return {"key": no, "name": name, "box": cat, "box_order": no,
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
                initial=initial, columns=2, views=[("Boxes", "box", ("My boxes", "Game boxes"))] if mine else None,
                note="The game's boxes are fixed lists of items. Your own boxes (made in the Supply Box tab) "
                     "come first. Search for an item to find the boxes that contain it.")


def pick_small_species(app, allowed, title="Choose a small monster", initial=None, note=None):
    """Small monsters that the game's quests use on the quest's map. ``allowed``: species -> number
    of game quests on that map that use it."""
    icons, dev = app.icons, app.dev_mode.get()
    entries = []
    for em, n in sorted(allowed.items(), key=lambda kv: G.mon_name(kv[0])):
        entries.append({"key": em, "name": G.mon_name(em),
                        "sub": _(f"used in {n} game quest{'s' if n != 1 else ''} here") + (f" · em{em:03d}" if dev else ""),
                        "search": f"{G.mon_name(em)} em{em:03d}" if dev else G.mon_name(em),
                        "icon": (lambda em=em: icons.monster(em, 54))})
    return _run(app, title=title, entries=entries, tile=(230, 64), icon_size=54, columns=3,
                initial=initial, dev=dev, note=note)
