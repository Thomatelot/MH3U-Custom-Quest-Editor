"""Quest editor page, laid out like the MH4U Custom Quest Editor:
a top bar (back, checks, undo, save), a quest card and the editing tabs
General / Monsters / Supply Box / Rewards / Text (+ Advanced in developer mode).
"""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from . import autofill, spawns, startpos, strays, supp, waves
from . import gamedata as G
from . import monsterpack
from . import helptext as H
from . import picker, theme
from .quest import LANG_NAMES, LANGS, MON_SLOTS, NANDO_MAX, QuestFormatError
from .validate import worst
from .widgets import ScrollFrame, Section, StatusDot, Tooltip, center_on, info, make_modal, parse_int

PATTERNS = {0: "One objective", 1: "Both objectives", 2: "Either objective"}
# Stamina values used by the game's own quests (see helptext 'Stamina')
STAMINA = {0: "Village", 1: "Port Low / High Rank", 2: "Port G Rank", 3: "Grudge Match / Challenge"}
# The record field names are the editor's historical ones; the game's own names of this part of the
# record are given in quest.py. The labels below say what the fields do.
OTHER_FIELDS = (("start_param", "Monster arrival pattern"), ("hagi_no", "Supply rank / story step"),
                ("prog_no", "Monster rank"), ("enemy_lv", "Intro cutscene"),
                ("special_flag", "Special flag"), ("special_cond", "Special condition"),
                ("special_cond2", "Special condition 2"), ("ren_pattern", "Rannyu_limite (0)"))
MODE_TYPES = (0x0001, 0x0081, 0x0101)        # objectives whose 'mode' means something
UP, DOWN = "▲", "▼"


def stars(n: int) -> str:
    return "★" * max(0, min(n, 10))


class RankDialog(tk.Toplevel):
    """'Fill automatically': pick the rank to copy from and see exactly what it is based on."""

    def __init__(self, app, title, intro, star, preview):
        super().__init__(app)
        self.withdraw()
        self.title(title)
        self.transient(app)
        self.configure(background=theme.color("bg"))
        self.result = None
        self.preview = preview
        f = ttk.Frame(self, padding=14)
        f.pack(fill="both")
        ttk.Label(f, text=intro, wraplength=460, justify="left").pack(anchor="w")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=10)
        ttk.Label(row, text="Rank").pack(side="left")
        self.cb = ttk.Combobox(row, state="readonly", width=26, values=[autofill.POOL_LABEL[p] for p in autofill.POOLS])
        self.cb.current(autofill.POOLS.index(autofill.pool_for_star(star)))
        self.cb.pack(side="left", padx=8)
        self.cb.bind("<<ComboboxSelected>>", self._show)
        self.what = ttk.Label(f, text="", wraplength=460, justify="left", style="Muted.TLabel")
        self.what.pack(anchor="w", pady=(0, 6))
        b = ttk.Frame(self, padding=(14, 0, 14, 14))
        b.pack(fill="x")
        self.ok_btn = ttk.Button(b, text="Fill", style="Accent.TButton", command=self._ok)
        self.ok_btn.pack(side="right")
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right", padx=6)
        self.bind("<Escape>", lambda _e: self.destroy())
        self._show()
        center_on(self, app)
        self.deiconify()
        make_modal(self)

    def pool(self):
        return autofill.POOLS[self.cb.current()]

    def _show(self, _e=None):
        text = self.preview(self.pool())
        self.what.configure(text=text or "The game has nothing to suggest for this rank.")
        self.ok_btn.state(["!disabled"] if text else ["disabled"])

    def _ok(self):
        self.result = self.pool()
        self.destroy()


def ask_rank(app, title, intro, star, preview):
    dlg = RankDialog(app, title, intro, star, preview)
    app.wait_window(dlg)
    return dlg.result


class StartDialog(tk.Toplevel):
    """Choose where a monster starts: the list of start positions on the left, the zone map
    (with its area numbers) on the right, like the MH4U editor."""

    def __init__(self, app, map_id, current, name, em=None):
        super().__init__(app)
        self.withdraw()
        self.title(f"Where {name} starts")
        self.transient(app)
        self.configure(background=theme.color("bg"))
        self.result = None
        self.map_id = map_id
        self.var = tk.IntVar(value=current)
        pack, _installed = app.monster_pack()
        self.areas = startpos.areas(em, map_id, pack) if em else None
        f = ttk.Frame(self, padding=14)
        f.pack(fill="both")
        left = ttk.Frame(f)
        left.pack(side="left", anchor="n")
        ttk.Label(left, text=f"{G.map_name(map_id)}: start position of {name}", style="H2.TLabel").pack(anchor="w")
        self.what = ttk.Label(left, text="", wraplength=380, justify="left", style="Muted.TLabel")
        if self.areas is not None:
            choices = list(range(len(self.areas)))
            if current not in choices:
                choices.append(current)
        else:
            choices = startpos.positions(map_id)
        for pos in choices:
            u = startpos.usage(map_id, pos)
            row = ttk.Frame(left)
            row.pack(anchor="w", fill="x", pady=1)
            if self.areas is not None:
                text = startpos.choice_text(pos, self.areas, map_id)
            else:
                text = startpos.label(pos) + (f"   ({u['n']} in the game)" if u else "   (not used on this map)")
            ttk.Radiobutton(row, text=text, value=pos, variable=self.var, command=self._show).pack(side="left")
        self.what.pack(anchor="w", pady=(10, 0))
        ttk.Label(left, text=(("The quest file stores a number; the game turns it into a start area with its own "
                               "table for this monster and map (read from the game's code). The map on the right "
                               "shows the area numbers.") if self.areas is not None else
                              ("The quest file stores this as a number only. The start areas of this monster on "
                               "this map are not known, so each number lists the game's own monsters that "
                               "start there.")),
                  wraplength=380, justify="left", style="Muted.TLabel").pack(anchor="w", pady=(10, 0))
        right = ttk.Frame(f)
        right.pack(side="left", padx=(18, 0), anchor="n")
        self._img = app.icons.map(map_id, 160)
        try:
            self._img = self._img.zoom(2)
        except tk.TclError:
            pass
        ttk.Label(right, image=self._img).pack()
        ttk.Label(right, text="Area numbers of the zone", style="Muted.TLabel").pack()
        b = ttk.Frame(self, padding=(14, 0, 14, 14))
        b.pack(fill="x")
        ttk.Button(b, text="OK", style="Accent.TButton", command=self._ok).pack(side="right")
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right", padx=6)
        self.bind("<Escape>", lambda _e: self.destroy())
        self._show()
        center_on(self, app)
        self.deiconify()
        make_modal(self)

    def _show(self):
        text = startpos.describe(self.map_id, self.var.get())
        if self.areas is not None:
            pos = self.var.get()
            text = (f"Starts in {startpos.area_label(self.map_id, self.areas[pos])} (number shown on the map). "
                    if pos < len(self.areas) else
                    "This position does not exist for this monster on this map: choose another one. ") + \
                (text if startpos.usage(self.map_id, pos) else "")
        self.what.configure(text=text)

    def _ok(self):
        self.result = self.var.get()
        self.destroy()


def tier_text(t: int) -> str:
    return "NIGHTMARE" if t == H.NIGHTMARE else H.tier_name(t)


# ======================================================================= base
class Tab(ttk.Frame):
    def __init__(self, parent, editor):
        super().__init__(parent)
        self.editor = editor
        self.app = editor.app
        self.loading = False
        self.bound: dict[str, tuple[tk.StringVar, ttk.Spinbox]] = {}
        self.hooks: dict[str, callable] = {}

    @property
    def q(self):
        return self.editor.quest

    @property
    def dev(self) -> bool:
        return self.app.dev_mode.get()

    def do_load(self, q):
        self.loading = True
        try:
            self.load(q)
        finally:
            self.loading = False

    def load(self, q):
        raise NotImplementedError

    def field(self, parent, row, label, name, tip=None, width=9, col=0, suffix=None):
        """Label + spinbox + (suffix) + (i), on one grid row of a card."""
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=col * 4, sticky="w",
                                                                padx=(0, 8), pady=3)
        var = tk.StringVar()
        sp = ttk.Spinbox(parent, textvariable=var, width=width, from_=0, to=65535)
        sp.grid(row=row, column=col * 4 + 1, sticky="w", pady=3)
        cell = ttk.Frame(parent, style="Card.TFrame")
        cell.grid(row=row, column=col * 4 + 2, sticky="w", padx=(4, 22))
        if suffix:
            ttk.Label(cell, text=suffix, style="Card.Muted.TLabel").pack(side="left")
        if tip:
            info(cell, tip, "Card.").pack(side="left", padx=4)
        var.trace_add("write", lambda *_: self._commit(name, var, sp))
        self.bound[name] = (var, sp)
        return sp

    def load_bound(self, q):
        for name, (var, sp) in self.bound.items():
            lo, hi = q.scalar_range(name)
            sp.configure(from_=lo, to=hi, style="TSpinbox")
            var.set(str(q.get(name)))

    def _commit(self, name, var, sp):
        if self.loading or self.q is None:
            return
        try:
            self.q.set(name, parse_int(var.get()))
        except (ValueError, QuestFormatError):
            sp.configure(style="Bad.TSpinbox")
            return
        sp.configure(style="TSpinbox")
        if name in self.hooks:
            self.hooks[name]()
        self.editor.changed()

    def scroll_body(self):
        sf = self.sf = ScrollFrame(self)
        sf.pack(fill="both", expand=True)
        body = ttk.Frame(sf.inner, padding=(12, 10))
        body.pack(fill="both", expand=True)
        return body


class IconButton(ttk.Button):
    """A button showing an icon and a name (opens a picker)."""

    def __init__(self, parent, command, width=24):
        super().__init__(parent, style="Tile.TButton", command=command, compound="left", width=width)

    def show(self, image, text):
        self._img = image
        self.configure(image=image or "", text="  " + text)


class Collapsible(Section):
    """A card whose body opens and closes with a ▼ / ▲ link in its title bar."""

    def __init__(self, parent, title, tip_text=None, opened=False):
        super().__init__(parent, title, tip_text)
        self.toggle_btn = ttk.Button(self.head, style="Link.TButton", command=self.toggle)
        self.toggle_btn.pack(side="right")
        self.opened = not opened
        self.toggle()

    def toggle(self, force=None):
        self.opened = (not self.opened) if force is None else force
        if self.opened:
            self.body.pack(fill="both", expand=True)
        else:
            self.body.pack_forget()
        self.toggle_btn.configure(text=f"Hide  {UP}" if self.opened else f"Show  {DOWN}")


def mult_text(row: int, col: int, what: str) -> str:
    r = G.nando_row(row)
    return f"{what} ×{r[col]:g}" if r else "rows go from 0 to 127"


# ==================================================================== General
class GeneralTab(Tab):
    def __init__(self, parent, editor):
        super().__init__(parent, editor)
        body = self.scroll_body()
        body.columnconfigure(0, weight=1, uniform="g")
        body.columnconfigure(1, weight=1, uniform="g")

        s1 = Section(body, "Quest")
        s1.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 10))
        g = s1.body
        r = 0
        if self.dev:
            ttk.Label(g, text="Quest number", style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=3)
            self.no_lab = ttk.Label(g, text="", style="Card.TLabel", font=theme.FONTS["bold"])
            self.no_lab.grid(row=r, column=1, sticky="w")
            cell = ttk.Frame(g, style="Card.TFrame")
            cell.grid(row=r, column=2, sticky="w", padx=4)
            self.no_btn = ttk.Button(cell, text="Change...", command=self.editor.app.change_number)
            self.no_btn.pack(side="left")
            info(cell, H.tip("quest_no"), "Card.").pack(side="left", padx=4)
            r += 1
        else:
            self.no_lab = self.no_btn = None
        ttk.Label(g, text="Star rank", style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=3)
        self.star = ttk.Combobox(g, state="readonly", width=16,
                                 values=[f"{n}  {stars(n)}" if n else "0" for n in range(0, 11)])
        self.star.grid(row=r, column=1, sticky="w")
        self.star.bind("<<ComboboxSelected>>", self._star)
        info(g, H.tip("star"), "Card.").grid(row=r, column=2, sticky="w", padx=4)
        r += 1
        ttk.Label(g, text="Map", style="Card.TLabel").grid(row=r, column=0, sticky="nw", pady=6)
        self.map_btn = IconButton(g, self._pick_map, width=20)
        self.map_btn.grid(row=r, column=1, sticky="w", pady=3)
        info(g, H.tip("map"), "Card.").grid(row=r, column=2, sticky="w", padx=4)
        r += 1
        ttk.Label(g, text="Hunters start", style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=3)
        self.hunt = ttk.Combobox(g, state="readonly", width=34)
        self.hunt.grid(row=r, column=1, sticky="w")
        self.hunt.bind("<<ComboboxSelected>>", self._hunt_pick)
        info(g, H.tip("supp_enemy_num"), "Card.").grid(row=r, column=2, sticky="w", padx=4)
        r += 1
        self.hunt_lab = ttk.Label(g, text="", style="Card.Muted.TLabel", wraplength=430, justify="left")
        self.hunt_lab.grid(row=r, column=0, columnspan=4, sticky="w", pady=(0, 4))
        self._hunt_values: list[int] = []
        r += 1
        self.field(g, r, "Time limit", "time_min", tip=lambda: H.tip("time_min"), suffix="minutes")
        self.hooks["time_min"] = self._sync_frozen
        r += 1
        self.frozen = tk.BooleanVar()
        fr = ttk.Frame(g, style="Card.TFrame")
        fr.grid(row=r, column=0, columnspan=4, sticky="w", pady=(0, 4))
        ttk.Checkbutton(fr, text="Frozen clock (sets 99 minutes)", variable=self.frozen,
                        style="Card.TCheckbutton", command=self._frozen).pack(side="left")
        info(fr, "Tested in the game: up to 98 minutes the clock counts down normally; from 99 minutes it is "
                 "frozen, so the quest can never time out (99 and 120 were tried). The box sets 99, the "
                 "lowest frozen value; untick it to go back to 50 minutes. 135 is reported by players to "
                 "freeze it too but is untested, and the highest value the game can take is unknown.",
             "Card.").pack(side="left", padx=4)

        s2 = Section(body, "Zenny and HR points")
        s2.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 10))
        g = s2.body
        money = lambda f: (lambda: H.tip(f) + "\n\n" + H.money_hint(f, self.q.get("star") if self.q else 1))
        self.field(g, 0, "Fee", "contract", tip=money("contract"), suffix="z")
        self.field(g, 1, "Reward", "reward_money", tip=money("reward_money"), suffix="z")
        self.field(g, 2, "Penalty", "penalty", tip=H.tip("penalty"), suffix="z")
        self.auto_pen = tk.BooleanVar(value=True)
        ttk.Checkbutton(g, text="Penalty = reward ÷ 3 (as in the game)", variable=self.auto_pen,
                        style="Card.TCheckbutton", command=self._auto_penalty).grid(
            row=3, column=0, columnspan=4, sticky="w", pady=(0, 4))
        self.field(g, 4, "HR points", "main_hrp", tip=money("main_hrp"))
        self.field(g, 5, "HR points on failure", "failure_hrp", tip=H.tip("failure_hrp"))
        self.hooks["reward_money"] = self._auto_penalty

        s3 = Section(body, "Objectives", H.tip("clr_pattern"))
        s3.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        g = s3.body
        self.pattern = tk.IntVar()
        seg = ttk.Frame(g, style="Card.TFrame")
        seg.grid(row=0, column=0, columnspan=8, sticky="w", pady=(0, 8))
        for val, text in PATTERNS.items():
            ttk.Radiobutton(seg, text=text, value=val, variable=self.pattern, style="Seg.TRadiobutton",
                            command=self._pattern).pack(side="left", padx=1)
        self.summary = ttk.Label(g, text="", style="Card.Accent.TLabel", wraplength=900, justify="left")
        self.summary.grid(row=1, column=0, columnspan=8, sticky="w", pady=(0, 8))
        for col, text in enumerate(("", "Type", "Target", "How it is counted", "", "Count")):
            if text:
                ttk.Label(g, text=text, style="Card.Muted.TLabel").grid(row=2, column=col, sticky="w")
        self.objs = [ObjectiveRow(g, self, 1, 3), ObjectiveRow(g, self, 2, 4)]
        self.win_lab = ttk.Label(g, text="", style="Card.TLabel", wraplength=900, justify="left")
        self.win_lab.grid(row=5, column=0, columnspan=8, sticky="w", pady=(8, 0))
        sync = ttk.Frame(g, style="Card.TFrame")
        sync.grid(row=6, column=0, columnspan=8, sticky="w", pady=(6, 0))
        ttk.Button(sync, text="Set the objectives from the monsters", command=self._sync_objectives).pack(side="left")
        info(sync, "Writes Objective A and B the way the game's multi-monster quests do: the targets are the "
                   "monsters of the last group that arrives (see 'How the monsters arrive' on the Monsters "
                   "tab), the count is how many of that species the quest has. The Monsters tab does this "
                   "for you whenever you change the monsters.", "Card.").pack(side="left", padx=4)

        s6 = Section(body, "Environment", H.ENV_TIP)
        s6.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        g = s6.body
        self.env = tk.IntVar()
        seg = ttk.Frame(g, style="Card.TFrame")
        seg.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        for val, text in ((0, "Stable"), (1, "Unstable")):
            ttk.Radiobutton(seg, text=text, value=val, variable=self.env, style="Seg.TRadiobutton",
                            command=self._env).pack(side="left", padx=1)
        self.env_text = ttk.Label(g, text="", style="Card.Muted.TLabel", wraplength=470, justify="left")
        self.env_text.grid(row=1, column=0, columnspan=4, sticky="w")
        self.env_opts = ttk.Frame(g, style="Card.TFrame")
        self.env_opts.grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))
        self.field(self.env_opts, 0, "Chance of roaming monsters", "nora_set_per", tip=H.tip("nora_set_per"),
                   width=6, suffix="%")
        self.field(self.env_opts, 1, "At most at the same time", "nora_set_max", tip=H.tip("nora_set_max"), width=6)
        self.hooks["nora_set_per"] = self._env_refresh
        self.env_list = ttk.Frame(self.env_opts, style="Card.TFrame")
        self.env_list.grid(row=2, column=0, columnspan=4, sticky="w", pady=(6, 0))
        ttk.Button(self.env_list, text="Roaming monsters like another game quest...", command=self._env_pick).pack(side="left")
        self.env_ref = ttk.Label(g, text="", style="Card.Accent.TLabel", wraplength=470, justify="left")
        self.env_ref.grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))
        if self.dev:
            dv = ttk.Frame(self.env_opts, style="Card.TFrame")
            dv.grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))
            for i, (f, lab) in enumerate((("nora_set_type", "Use roaming list"), ("nora_per_type", "Second %"),
                                          ("nora_set_table", "List number"), ("nora_pekko", "Always comes"))):
                self.field(dv, i // 2, lab, f, tip=H.tip(f), width=6, col=i % 2)
        if self.dev:
            s4 = Collapsible(body, "Other gameplay settings",
                             "Rarely changed settings. Each (i) says what is known about the field and "
                             "which values the game's own quests use. Keep the values of the quest you "
                             "copied unless you know what you are doing.", opened=True)
            s4.grid(row=3, column=0, columnspan=2, sticky="nsew")
            half = (len(OTHER_FIELDS) + 1) // 2
            for i, (field, label) in enumerate(OTHER_FIELDS):
                self.field(s4.body, i % half, label, field, tip=H.tip(field), col=i // half)

    def load(self, q):
        self.load_bound(q)
        if self.no_lab is not None:
            self.no_lab.configure(text=str(q.get("quest_no")))
            self.no_btn.configure(state="normal" if self.app.source_can_create() else "disabled")
        self.star.current(max(0, min(10, q.get("star"))))
        m = q.get("map")
        self.map_btn.show(self.app.icons.map(m, 64), G.map_name(m) + (f"  (map {m})" if self.dev else ""))
        self._hunt_load(q)
        self.auto_pen.set(q.get("penalty") == math.ceil(q.get("reward_money") / 3))
        self.pattern.set(q.get("clr_pattern") if q.get("clr_pattern") in PATTERNS else 0)
        for o in self.objs:
            o.load(q)
        self.refresh_summary()
        self._env_refresh()
        self._sync_frozen()

    def refresh_summary(self):
        if self.q is not None:
            self.summary.configure(text="In the game:  " + G.objectives_sentence(self.q))
            self.win_lab.configure(text=waves.win_text(self.q))

    # ----- where the hunters start (the field the game calls StartParam)
    def _hunt_load(self, q):
        v, m = q.get("supp_enemy_num"), q.get("map")
        values = sorted(set(startpos.HUNTER_CHOICES) | {v})
        self._hunt_values = values
        self.hunt.configure(values=[f"{x}  {startpos.HUNTER_CHOICES.get(x, '(not used by the game)')}"
                                    for x in values])
        self.hunt.current(values.index(v))
        warn = startpos.hunter_warning(m, v)
        self.hunt_lab.configure(text=warn or startpos.hunter_text(m, v),
                                style="Card.Warn.TLabel" if warn else "Card.Muted.TLabel")

    def _hunt_pick(self, _e=None):
        i = self.hunt.current()
        if self.loading or self.q is None or not 0 <= i < len(self._hunt_values):
            return
        self.q.set("supp_enemy_num", self._hunt_values[i])
        self._hunt_load(self.q)
        self.editor.changed()

    # ----- frozen clock
    def _sync_frozen(self):
        if self.q is not None:
            self.frozen.set(self.q.get("time_min") >= 99)

    def _frozen(self):
        if self.q is None or self.loading:
            return
        self.q.set("time_min", 99 if self.frozen.get() else 50)
        was, self.loading = self.loading, True
        self.bound["time_min"][0].set(str(self.q.get("time_min")))
        self.loading = was
        self.editor.changed()

    def _star(self, _e=None):
        if not self.loading and self.q is not None:
            self.q.set("star", self.star.current())
            self.editor.changed()

    def _pick_map(self):
        if self.q is None:
            return
        m = picker.pick_map(self.app, self.q.get("map"))
        if m is not None and m != self.q.get("map"):
            self._change_map(m)

    def _change_map(self, m):
        q = self.q
        q.set("map", m)
        for i, mon in enumerate(q.monsters):
            if mon["Type"] and mon["Starttype"]:
                q.set_monster(i, Starttype=0)             # start numbers belong to the old map
        refs = spawns.reference_lists(m, q.get("star"), autofill.pool_for_star(q.get("star"))) if spawns.available() else []
        if spawns.readable(q) and refs and messagebox.askyesno(
                "New map", f"The small monsters' places (and the roaming monsters) belong to the old map.\n\n"
                f"Replace them with the game's lists for {G.map_name(m)}?\n\n"
                "(Recommended: places taken from another map can put small monsters inside walls.)", parent=self):
            e = refs[0]
            spawns.fill_from(q, e)
            for field, em in zip(("main_zako1", "main_zako2"), e["main"]):
                q.set(field, em)
            if strays.is_unstable(q):
                sref = strays.references(m, q.get("star"))
                if sref:
                    strays.apply(q, sref[0])
                else:
                    strays.make_stable(q)
        self.editor.reload_tabs()
        self.editor.changed()

    # ----- objectives from the monsters
    def _sync_objectives(self):
        q = self.q
        if q is None:
            return
        if not waves.used_slots(q):
            messagebox.showinfo("Objectives", "Add a large monster first.", parent=self)
            return
        if not waves.sync_objectives(q):
            messagebox.showinfo("Objectives", "Objective A is not a hunt (it is a delivery or a siege), so "
                                "the monsters cannot decide it. Change its type to Hunt first.", parent=self)
            return
        self.editor.reload_tabs()
        self.editor.changed()

    # ----- environment (roaming monsters)
    def _env_refresh(self):
        q = self.q
        if q is None:
            return
        unstable = strays.is_unstable(q)
        self.env.set(1 if unstable else 0)
        if unstable:
            self.env_opts.grid()
            ref = strays.reference_of(q)
            self.env_text.configure(text=strays.describe(q))
            if ref:
                self.env_ref.configure(text=f"Roaming monsters: the same list as the game's quest '{ref['name']}'. "
                                            "Which species roam is stored in the game, not in the quest file, so "
                                            "it cannot be shown or chosen here.")
            else:
                self.env_ref.configure(text="Roaming-monster list number " + str(q.get("nora_set_table"))
                                            + ": no game quest on this zone uses it, so it may not exist.",
                                       style="Card.Danger.TLabel")
                return
            self.env_ref.configure(style="Card.Accent.TLabel")
        else:
            self.env_opts.grid_remove()
            self.env_text.configure(text=strays.describe(q))
            self.env_ref.configure(text="")

    def _env(self):
        q = self.q
        if q is None or self.loading:
            return
        if self.env.get() == 0:
            strays.make_stable(q)
        else:
            refs = strays.references(q.get("map"), q.get("star"))
            if not refs:
                messagebox.showinfo("Environment", f"None of the game's quests on {G.map_name(q.get('map'))} "
                                    "is Unstable, so there is no roaming-monster list to reuse there.",
                                    parent=self)
                self.env.set(0)
                return
            strays.apply(q, refs[0])
        self.editor.reload_tabs()
        self.editor.changed()

    def _env_pick(self):
        q = self.q
        if q is None:
            return
        refs = strays.references(q.get("map"), q.get("star"))
        if not refs:
            return
        opts = []
        for i, s in enumerate(refs):
            opts.append({"key": i, "name": s["name"], "cat": "All",
                         "sub": f"{s['star']} star · {s['per']} % · up to {s['max']} at once",
                         "search": s["name"],
                         "icon": (lambda s=s: self.app.icons.map(s['map'], 54))})
        i = picker._run(self.app, title="Roaming monsters like...", entries=opts, tile=(480, 66), icon_size=54,
                        columns=1, initial=0, note="Game quests on this zone that are Unstable, closest star rank "
                        "first. The roaming-monster list is stored in the game: you reuse the one of the quest you pick, "
                        "you cannot choose the species.")
        if i is None:
            return
        strays.apply(q, refs[i])
        self.editor.reload_tabs()
        self.editor.changed()

    def _auto_penalty(self):
        if self.q is None or not self.auto_pen.get():
            return
        self.q.set("penalty", math.ceil(self.q.get("reward_money") / 3))
        was, self.loading = self.loading, True
        self.bound["penalty"][0].set(str(self.q.get("penalty")))
        self.loading = was
        if not was:
            self.editor.changed()

    def _pattern(self):
        if self.q is not None and not self.loading:
            self.q.set("clr_pattern", self.pattern.get())
            self.refresh_summary()
            self.editor.changed()


class ObjectiveRow:
    """Objective A or B: type, target (monster or item), which monsters, count."""

    def __init__(self, g, tab, which, row):
        self.tab, self.which = tab, which
        ttk.Label(g, text=f"Objective {'AB'[which - 1]}", style="Card.H3.TLabel").grid(
            row=row, column=0, sticky="w", pady=4, padx=(0, 10))
        self.codes = list(G.OBJ_NAMES)
        self.type = ttk.Combobox(g, state="readonly", width=24, values=list(G.OBJ_NAMES.values()))
        self.type.grid(row=row, column=1, sticky="w")
        self.type.bind("<<ComboboxSelected>>", self._type)
        self.target = IconButton(g, self._pick, width=22)
        self.target.grid(row=row, column=2, sticky="w", padx=8)
        self.modes = list(G.OBJ_MODES)
        self.mode = ttk.Combobox(g, state="readonly", width=28, values=list(G.OBJ_MODES.values()))
        self.mode.grid(row=row, column=3, sticky="w")
        self.mode.bind("<<ComboboxSelected>>", self._mode)
        info(g, H.tip("objective"), "Card.").grid(row=row, column=4, sticky="w", padx=4)
        self.count = tk.StringVar()
        self.count_sp = ttk.Spinbox(g, textvariable=self.count, from_=0, to=9999, width=6)
        self.count_sp.grid(row=row, column=5, sticky="w", padx=(4, 0))
        info(g, H.tip("obj_count"), "Card.").grid(row=row, column=6, sticky="w", padx=4)
        self.count.trace_add("write", lambda *_: self._commit())
        self.dev = ttk.Label(g, text="", style="Card.Muted.TLabel")
        self.dev.grid(row=row, column=7, sticky="w", padx=8)

    def load(self, q):
        typ, mode, tid, cnt = q.objective(self.which)
        if typ in self.codes:
            self.type.current(self.codes.index(typ))
        else:
            self.type.set(f"Other (0x{typ:04X})" if self.tab.dev else "Special objective")
        if typ in MODE_TYPES:
            self.mode.state(["!disabled"])
            if mode in self.modes:
                self.mode.current(self.modes.index(mode))
            else:
                self.mode.set(f"Other ({mode})" if self.tab.dev else "Special")
        else:
            self.mode.set("")
            self.mode.state(["disabled"])
        self.count.set(str(cnt))
        self.count_sp.state(["!disabled"] if typ else ["disabled"])
        self._show_target(typ, tid)
        self.dev.configure(text=f"type 0x{typ:04X} · mode {mode} · id {tid}" if self.tab.dev else "")

    def _show_target(self, typ, tid):
        icons = self.tab.app.icons
        if typ in G.OBJ_ITEM:
            self.target.show(icons.item(tid), G.item_name(tid))
            self.target.state(["!disabled"])
        elif typ in G.OBJ_MONSTER:
            self.target.show(icons.monster(tid, 27), G.mon_name(tid))
            self.target.state(["!disabled"])
        else:
            self.target.show(None, "-")
            self.target.state(["disabled"])

    def _set(self, typ=None, tid=None, cnt=None, mode=None):
        q = self.tab.q
        t0, m0, id0, c0 = q.objective(self.which)
        q.set_objective(self.which, t0 if typ is None else typ, id0 if tid is None else tid,
                        c0 if cnt is None else cnt, m0 if mode is None else mode)
        self.tab.do_load(q)
        self.tab.editor.changed()

    def _type(self, _e=None):
        if self.tab.loading or self.tab.q is None:
            return
        typ = self.codes[self.type.current()]
        _t, mode, tid, cnt = self.tab.q.objective(self.which)
        if typ and cnt <= 0:
            cnt = 1
        if typ in G.OBJ_MONSTER and tid not in G.MONSTERS:
            mons = [m["Type"] for m in self.tab.q.monsters if m["Type"]]
            tid = mons[0] if mons else 0
        if typ in G.OBJ_ITEM and not (0 < tid < len(G.ITEMS)):
            tid = 1
        if typ not in MODE_TYPES:
            mode = 0
        self._set(typ=typ, tid=tid, cnt=cnt, mode=mode)

    def _mode(self, _e=None):
        if self.tab.loading or self.tab.q is None:
            return
        self._set(mode=self.modes[self.mode.current()])

    def _pick(self):
        q = self.tab.q
        typ, _m, tid, _c = q.objective(self.which)
        if typ in G.OBJ_ITEM:
            v = picker.pick_item(self.tab.app, tid, title="Item to deliver")
        else:
            v = picker.pick_monster(self.tab.app, tid, title="Objective target")
        if v is not None:
            self._set(tid=v)

    def _commit(self):
        if self.tab.loading or self.tab.q is None:
            return
        try:
            cnt = parse_int(self.count.get())
            typ, mode, tid, _c = self.tab.q.objective(self.which)
            self.tab.q.set_objective(self.which, typ, tid, cnt, mode)
        except (ValueError, QuestFormatError):
            return
        self.tab.refresh_summary()
        self.tab.editor.changed()


# =================================================================== Monsters
class MonsterCard(ttk.Frame):
    STAT_ROWS = (("Nando_hp", "Health"), ("Nando_at", "Attack"), ("Nando_etc", "Toughness"))

    def __init__(self, parent, tab, slot):
        super().__init__(parent, style="Box.TFrame", padding=(12, 10))
        self.tab, self.slot = tab, slot
        self.vars: dict[str, tk.IntVar] = {}
        head = ttk.Frame(self, style="Card.TFrame")
        head.pack(fill="x")
        self.icon = ttk.Label(head, style="Card.TLabel")
        self.icon.pack(side="left")
        self._icon_tip = ""
        Tooltip(self.icon, lambda: self._icon_tip)
        names = ttk.Frame(head, style="Card.TFrame")
        names.pack(side="left", padx=10, fill="x", expand=True)
        self.name = ttk.Label(names, text="", style="Card.H2.TLabel")
        self.name.pack(anchor="w")
        self.tier_lab = ttk.Label(names, text="", style="Card.Accent.TLabel")
        self.tier_lab.pack(anchor="w")
        self.spawn = ttk.Label(names, text="", style="Card.Muted.TLabel", wraplength=300)
        self.spawn.pack(anchor="w")
        btns = ttk.Frame(head, style="Card.TFrame")
        btns.pack(side="right")
        ttk.Button(btns, text="Change...", command=self._change).pack(fill="x")
        ttk.Button(btns, text="Copy from a quest...", command=self._copy).pack(fill="x", pady=2)
        ttk.Button(btns, text="Remove", command=self._remove).pack(fill="x")
        order = ttk.Frame(btns, style="Card.TFrame")
        order.pack(fill="x", pady=(2, 0))
        ttk.Button(order, text="◀", width=3, command=lambda: self._shift(-1)).pack(side="left", expand=True, fill="x")
        ttk.Button(order, text="▶", width=3, command=lambda: self._shift(1)).pack(side="left", expand=True, fill="x")

        g = ttk.Frame(self, style="Card.TFrame")
        g.pack(fill="x", pady=(8, 0))
        self.count_w = self._spin(g, 0, 0, "Count", "Num", 1, 99)
        self._spin(g, 0, 3, "Size %", "Size", 0, 255)
        sz = ttk.Frame(g, style="Card.TFrame")
        sz.grid(row=1, column=0, columnspan=6, sticky="w", pady=(4, 0))
        ttk.Label(sz, text="Size like", style="Card.TLabel").pack(side="left")
        self.size_pre = ttk.Combobox(sz, state="readonly", width=22, values=[p[0] for p in H.SIZE_PRESETS])
        self.size_pre.pack(side="left", padx=6)
        self.size_pre.bind("<<ComboboxSelected>>", self._size_preset)
        info(sz, H.SIZE_TIP, "Card.").pack(side="left")
        sp_row = ttk.Frame(g, style="Card.TFrame")
        sp_row.grid(row=2, column=0, columnspan=6, sticky="w", pady=(4, 0))
        ttk.Label(sp_row, text="Starts in", style="Card.TLabel").pack(side="left")
        self.start_box = ttk.Combobox(sp_row, state="readonly", width=38)
        self.start_box.pack(side="left", padx=6)
        self.start_box.bind("<<ComboboxSelected>>", self._start_pick)
        ttk.Button(sp_row, text="Map...", width=6, command=self._start).pack(side="left")
        info(sp_row, H.tip("Starttype"), "Card.").pack(side="left", padx=4)
        self._start_values: list[int] = []
        pre = ttk.Frame(self, style="Card.TFrame")
        pre.pack(fill="x", pady=(8, 2))
        ttk.Label(pre, text="Strength like", style="Card.TLabel").pack(side="left")
        self.preset = ttk.Combobox(pre, state="readonly", width=20,
                                   values=[H.group_label(k) for k in H.group_keys()])
        self.preset.pack(side="left", padx=6)
        self.preset.bind("<<ComboboxSelected>>", self._preset)
        info(pre, "Sets Health, Attack, Toughness (and the hidden stamina and size settings) to the typical "
                  "values of the game's own quests of that hub and star rank.", "Card.").pack(side="left")
        self.stats = {}
        st = ttk.Frame(self, style="Card.TFrame")
        st.pack(fill="x")
        st.columnconfigure(2, weight=1)
        for r, (field, label) in enumerate(self.STAT_ROWS):
            ttk.Label(st, text=label, style="Card.TLabel").grid(row=r * 2, column=0, sticky="w")
            info(st, H.stat_tip(field), "Card.").grid(row=r * 2, column=1, sticky="w", padx=4)
            var = tk.IntVar()
            self.vars[field] = var
            sc = ttk.Scale(st, from_=0, to=NANDO_MAX, orient="horizontal", variable=var,
                           command=lambda v, f=field: self._scale(f, v))
            sc.grid(row=r * 2, column=2, sticky="ew", padx=6)
            sp = ttk.Spinbox(st, from_=0, to=NANDO_MAX, width=5, textvariable=var,
                             command=lambda f=field: self._commit(f))
            sp.grid(row=r * 2, column=3)
            sp.bind("<KeyRelease>", lambda _e, f=field: self._commit(f))
            lab = ttk.Label(st, text="", style="Card.Muted.TLabel")
            lab.grid(row=r * 2 + 1, column=0, columnspan=4, sticky="w", pady=(0, 4))
            self.stats[field] = lab
        self.stamina = self.more_btn = self.more = self.start_btn = None
        self.more_open = False
        if tab.dev:                       # obscure, almost identical in every quest: developer mode only
            sm = ttk.Frame(self, style="Card.TFrame")
            sm.pack(fill="x", pady=(4, 0))
            ttk.Label(sm, text="Stamina", style="Card.TLabel").pack(side="left")
            self.stamina = ttk.Combobox(sm, state="readonly", width=26)
            self.stamina.pack(side="left", padx=6)
            self.stamina.bind("<<ComboboxSelected>>", self._stamina)
            info(sm, H.tip("Stamina"), "Card.").pack(side="left")
            self.more_btn = ttk.Button(sm, text="", style="Link.TButton", command=self._toggle)
            self.more_btn.pack(side="right")
            self.more = ttk.Frame(self, style="Card.TFrame")
            self._spin(self.more, 0, 0, "Start type", "Starttype", 0, 255)
            self.start_btn = ttk.Button(self.more, text="Start positions on the map...", command=self._start)
            self.start_btn.grid(row=2, column=0, columnspan=6, sticky="w", pady=(4, 0))
            self._spin(self.more, 0, 3, "Size spread", "Sizeparam", 0, 255)
            self._spin(self.more, 1, 0, "Set type", "Settype", 0, 255)
            self._spin(self.more, 1, 3, "Nando2", "Nando2", 0, 255)
            self.more_open = True
            self._toggle()

    def _spin(self, g, row, col, label, field, lo, hi):
        ttk.Label(g, text=label, style="Card.TLabel").grid(row=row, column=col, sticky="w", pady=2)
        var = tk.IntVar()
        self.vars[field] = var
        sp = ttk.Spinbox(g, from_=lo, to=hi, width=6, textvariable=var, command=lambda: self._commit(field))
        sp.grid(row=row, column=col + 1, sticky="w", padx=4)
        sp.bind("<KeyRelease>", lambda _e: self._commit(field))
        tip = info(g, H.tip(field), "Card.")
        tip.grid(row=row, column=col + 2, sticky="w", padx=(0, 18))
        return [g.grid_slaves(row=row, column=col)[0], sp, tip]

    def _toggle(self, force=None):
        if self.more is None:
            return
        self.more_open = (not self.more_open) if force is None else force
        if self.more_open:
            self.more.pack(fill="x", pady=(6, 0))
        else:
            self.more.pack_forget()
        self.more_btn.configure(text="Spawn and size details  " + (UP if self.more_open else DOWN))

    @property
    def q(self):
        return self.tab.q

    def _stamina_values(self):
        dev = self.tab.dev
        return [f"{k} - {v}" if dev else v for k, v in STAMINA.items()]

    def load(self, m, number=None):
        app = self.tab.app
        em = m["Type"]
        self._img = app.icons.monster(em, 54)
        self.icon.configure(image=self._img)
        self._icon_tip = app.icons.monster_note(em) or G.mon_name(em)
        label = G.mon_name(em)
        if self.tab.dev:
            label += f"   em{em:03d}"
        if number:
            label = f"#{number}   {label}"
        self.name.configure(text=label)
        where = G.map_name(self.q.get("map"))
        pack, installed = app.monster_pack()
        status, _added = monsterpack.pair_status(em, self.q.get("map"), pack)
        if status == "missing":
            self.spawn.configure(text=f"Can not start on {where}: the game skips it (Monster pack page)",
                                 style="Card.Danger.TLabel")
        elif status == "pack":
            self.spawn.configure(text=f"On {where} thanks to the Monster pack (untested)"
                                 + ("" if installed else " - not installed!"), style="Card.Warn.TLabel")
        elif status == "unknown":
            self.spawn.configure(text="Spawn data not known for this map", style="Card.Muted.TLabel")
        else:
            self.spawn.configure(text=f"Appears on {where}", style="Card.Ok.TLabel")
        for f, var in self.vars.items():
            var.set(m[f])
        if self.stamina is not None:
            self.stamina.configure(values=self._stamina_values())
            st = m["Stamina"]
            if st in STAMINA:
                self.stamina.current(list(STAMINA).index(st))
            else:
                self.stamina.set(f"{st} (not used by the game)")
        self._fill_starts(m, pack)
        self.preset.set("")
        match = [p[0] for p in H.SIZE_PRESETS if p[1] == m["Size"]]
        self.size_pre.set(match[0] if match else f"Custom ({m['Size']} %)")
        self._describe(m)
        if self.start_btn is not None:
            ar = startpos.areas(em, self.q.get("map"), pack)
            where_txt = (f", {startpos.area_label(self.q.get('map'), ar[m['Starttype']])}"
                         if ar is not None and m["Starttype"] < len(ar) else
                         (", does not exist here" if ar is not None else ""))
            self.start_btn.configure(text=f"Start positions on the map...  (now: {startpos.label(m['Starttype'])}{where_txt})")
        self.set_count_visible(self.tab.dev or self.tab.n_large <= 1)
        if self.tab.dev and self.more is not None and not self.more_open:
            self._toggle(True)

    def set_count_visible(self, show: bool) -> None:
        for w in self.count_w:
            if show:
                w.grid()
            else:
                w.grid_remove()

    def _describe(self, m):
        d = H.describe_stats(m["Type"], m["Nando_hp"], m["Nando_at"], m["Nando_etc"], self.q.get("category"))
        if not d:
            for lab in self.stats.values():
                lab.configure(text="Rows go from 0 to 127")
            self.tier_lab.configure(text="")
            return
        for field, key, tkey in (("Nando_hp", "hp", "hp_t"), ("Nando_at", "atk", "atk_t"),
                                 ("Nando_etc", "dmg", "dmg_t")):
            t = d[tkey]
            lab = self.stats[field]
            like = f"  ·  {d[key + '_like']}" if self.tab.dev else ""
            lab.configure(text=f"{d[key]}  ·  {tier_text(t)}{like}",
                          style="Card.Danger.TLabel" if t == H.NIGHTMARE else "Card.Muted.TLabel")
        top = H.monster_tier(m)
        self.tier_lab.configure(text=f"Difficulty: {tier_text(top)}",
                                style="Card.Danger.TLabel" if top == H.NIGHTMARE else "Card.Accent.TLabel")

    def _scale(self, field, value):
        v = int(float(value))
        if self.vars[field].get() != v:
            self.vars[field].set(v)
        self._commit(field)

    def _commit(self, field):
        if self.tab.loading or self.q is None:
            return
        try:
            v = int(self.vars[field].get())
            if self.q.monsters[self.slot][field] == v:
                return
            self.q.set_monster(self.slot, **{field: v})
        except (ValueError, tk.TclError, QuestFormatError):
            return
        self._describe(self.q.monsters[self.slot])
        self.tab.editor.changed()

    def _fill_starts(self, m, pack):
        """The 'Starts in' list: the start points the game has for this monster on this map."""
        mp = self.q.get("map")
        ar = startpos.areas(m["Type"], mp, pack)
        values = list(range(len(ar))) if ar is not None else startpos.positions(mp)
        if m["Starttype"] not in values:
            values.append(m["Starttype"])
        self._start_values = values
        self.start_box.configure(values=[startpos.choice_text(v, ar, mp) for v in values])
        self.start_box.current(values.index(m["Starttype"]))

    def _start_pick(self, _e=None):
        i = self.start_box.current()
        m = self.q.monsters[self.slot]
        if 0 <= i < len(self._start_values) and self._start_values[i] != m["Starttype"]:
            self.q.set_monster(self.slot, Starttype=self._start_values[i])
            self.tab.do_load(self.q)
            self.tab.editor.changed()

    def _start(self):
        m = self.q.monsters[self.slot]
        dlg = StartDialog(self.tab.app, self.q.get("map"), m["Starttype"], G.mon_name(m["Type"]), em=m["Type"])
        self.tab.wait_window(dlg)
        if dlg.result is not None and dlg.result != m["Starttype"]:
            self.q.set_monster(self.slot, Starttype=dlg.result)
            self.tab.do_load(self.q)
            self.tab.editor.changed()

    def _shift(self, d):
        self.tab.shift(self.slot, d)

    def _stamina(self, _e=None):
        i = self.stamina.current()
        if i < 0:
            return
        self.q.set_monster(self.slot, Stamina=list(STAMINA)[i])
        self.tab.editor.changed()

    def _preset(self, _e=None):
        key = H.group_keys()[self.preset.current()]
        hp, at, df = H.preset_rows(key)
        self.q.set_monster(self.slot, Nando_hp=hp, Nando_at=at, Nando_etc=df, **H.preset_extra(key))
        self.tab.do_load(self.q)
        self.preset.set(H.group_label(key))
        self.tab.editor.changed()

    def _size_preset(self, _e=None):
        i = self.size_pre.current()
        if i < 0:
            return
        _label, size, spread = H.SIZE_PRESETS[i]
        extra = {} if spread is None else {"Sizeparam": spread}
        self.q.set_monster(self.slot, Size=size, **extra)
        self.tab.do_load(self.q)
        self.tab.editor.changed()

    def _change(self):
        em = picker.pick_monster(self.tab.app, self.q.monsters[self.slot]["Type"],
                                 title=f"Large monster {self.slot + 1}")
        if em is not None and em != self.q.monsters[self.slot]["Type"]:
            self.tab.set_species(self.slot, em)

    def _copy(self):
        self.tab.copy_from(self.slot)

    def _remove(self):
        self.tab.remove(self.slot)


class SpawnList(ttk.Frame):
    """The small monsters of the quest: every species of its spawn list with the number of places
    where it can appear, and the buttons to add, replace, remove or refill them."""

    def __init__(self, parent, tab):
        super().__init__(parent, style="Card.TFrame")
        self.tab = tab
        head = ttk.Frame(self, style="Card.TFrame")
        head.pack(anchor="w", fill="x")
        ttk.Label(head, text="Small monsters in the zone", style="Card.Muted.TLabel").pack(side="left")
        info(head, H.SPAWN_TIP, "Card.").pack(side="left", padx=4)
        self.rows = ttk.Frame(self, style="Card.TFrame")
        self.rows.pack(anchor="w", pady=(4, 0))
        bar = ttk.Frame(self, style="Card.TFrame")
        bar.pack(anchor="w", pady=(8, 0))
        self.add_btn = ttk.Button(bar, text="+  Add a species...", command=self.add)
        self.add_btn.pack(side="left")
        self.fill_btn = ttk.Button(bar, text="Fill from zone and rank...", command=self.fill)
        self.fill_btn.pack(side="left", padx=6)
        info(bar, H.SPAWN_FILL_TIP, "Card.").pack(side="left")
        self.note = ttk.Label(self, style="Card.Muted.TLabel", wraplength=560, justify="left", text="")
        self.note.pack(anchor="w", pady=(6, 0))
        self._imgs = []

    @property
    def q(self):
        return self.tab.q

    def load(self, q):
        for w in self.rows.winfo_children():
            w.destroy()
        self._imgs = []
        ok = spawns.readable(q) and spawns.available()
        counts = spawns.species(q) if ok else {}
        icons = self.tab.app.icons
        for r, (em, n) in enumerate(sorted(counts.items(), key=lambda kv: (-kv[1], G.mon_name(kv[0])))):
            img = icons.monster(em, 27)
            self._imgs.append(img)
            ttk.Label(self.rows, image=img, style="Card.TLabel").grid(row=r, column=0, padx=(0, 6), pady=1)
            label = G.mon_name(em) + (f"   em{em:03d}" if self.tab.dev else "")
            ttk.Label(self.rows, text=label, style="Card.TLabel", width=22).grid(row=r, column=1, sticky="w")
            ttk.Label(self.rows, text=f"{n} place{'s' if n != 1 else ''}", style="Card.Muted.TLabel",
                      width=10).grid(row=r, column=2, sticky="w")
            ttk.Button(self.rows, text="Change...", command=lambda e=em: self.change(e)).grid(row=r, column=3, padx=2)
            ttk.Button(self.rows, text="Remove", command=lambda e=em: self.remove(e)).grid(row=r, column=4, padx=2)
        on_map = bool(spawns.species_on_map(q.get("map"))) if spawns.available() else False
        for b in (self.add_btn, self.fill_btn):
            b.state(["!disabled"] if ok and on_map else ["disabled"])
        if not spawns.available():
            self.note.configure(text="The game's small-monster lists are missing from this copy of the editor.")
        elif not spawns.readable(q):
            self.note.configure(text="This quest has no small-monster list that the editor can read.")
        elif not on_map:
            self.note.configure(text=f"The game's own quests have no small monsters on {G.map_name(q.get('map'))}.")
        elif not counts:
            self.note.configure(text="No small monster at all: the zone will be empty of them. Use 'Fill from "
                                     "zone and rank' or add a species.")
        else:
            self.note.configure(text=f"{sum(counts.values())} places, {len(counts)} species. "
                                     f"Room for {spawns.room(q)} more places in the quest file.")

    # ---- actions
    def _done(self, q):
        self._fix_main(q)
        self.tab.editor.reload_tabs()
        self.tab.editor.changed()

    @staticmethod
    def _fix_main(q):
        have = spawns.species(q)
        if not have:
            return
        used = [q.get("main_zako1"), q.get("main_zako2")]
        for i, field in enumerate(("main_zako1", "main_zako2")):
            if used[i] and used[i] not in have:
                other = used[1 - i]
                pick = next((em for em, _n in have.most_common() if em != other), 0)
                q.set(field, pick)
                used[i] = pick

    def _allowed(self, exclude=()):
        return {em: n for em, n in spawns.species_on_map(self.q.get("map")).items() if em not in exclude}

    def change(self, em):
        q = self.q
        allowed = self._allowed(exclude=set(spawns.species(q)))
        if not allowed:
            messagebox.showinfo("Small monsters", "There is no other small monster that the game's quests "
                                f"use on {G.map_name(q.get('map'))}.", parent=self.tab)
            return
        new = picker.pick_small_species(self.tab.app, allowed, title=f"Replace {G.mon_name(em)} with...",
                                        note="Its places in the zone are kept, only the species changes. "
                                             "Only species that the game's quests use on this map are listed.")
        if new is None:
            return
        spawns.change(q, em, new)
        self._done(q)

    def remove(self, em):
        q = self.q
        spawns.remove(q, em)
        self._done(q)

    def add(self):
        q = self.q
        allowed = self._allowed(exclude=set(spawns.species(q)))
        if not allowed:
            messagebox.showinfo("Small monsters", "Every small monster that the game's quests use on "
                                f"{G.map_name(q.get('map'))} is already in the list.", parent=self.tab)
            return
        em = picker.pick_small_species(self.tab.app, allowed, title="Add a small monster",
                                       note="Its places are copied from the game's own quest on this map. "
                                            "Only species that the game's quests use here are listed.")
        if em is None:
            return
        try:
            spawns.add_species(q, em, q.get("star"), autofill.pool_for_star(q.get("star")))
        except QuestFormatError as e:
            messagebox.showwarning("Small monsters", str(e), parent=self.tab)
            return
        self._done(q)

    def fill(self):
        q = self.q
        mp, star = q.get("map"), q.get("star")
        pool = ask_rank(self.tab.app, "Small monsters", "Fill the small monsters of this quest from the game's "
                        f"own quests on {G.map_name(mp)}.", star,
                        lambda p: f"{len(spawns.reference_lists(mp, star, p))} game quests on this zone to choose from.")
        if pool is None:
            return
        refs = spawns.reference_lists(mp, star, pool)
        if not refs:
            return
        opts = []
        for i, e in enumerate(refs):
            names = ", ".join(G.mon_name(em) for em, _n in spawns.Counter(
                spawns.em_of(r) for r in e["recs"] if spawns.em_of(r)).most_common())
            opts.append({"key": i, "name": e["name"], "sub": f"{e['star']} star · {e['n']} places · {names}",
                         "cat": "All", "search": f"{e['name']} {names}",
                         "icon": (lambda e=e: self.tab.app.icons.monster(
                             next((spawns.em_of(r) for r in e["recs"] if spawns.em_of(r)), 0), 54))})
        pick = picker._run(self.tab.app, title="Copy the small monsters of a game quest", entries=opts,
                           tile=(480, 66), icon_size=54, columns=1, initial=0,
                           note=f"Closest rank first. Everything stays editable afterwards.")
        if pick is None:
            return
        entry = refs[pick]
        try:
            spawns.fill_from(q, entry)
        except QuestFormatError as e:
            messagebox.showwarning("Small monsters", str(e), parent=self.tab)
            return
        for field, em in zip(("main_zako1", "main_zako2"), entry["main"]):
            q.set(field, em)
        res = autofill.small_monsters(mp, pool)
        if res:
            for f in ("zako_nando_hp", "zako_nando_at", "zako_nando_etc"):
                q.set(f, res[0][f])
        self._done(q)


class MonstersTab(Tab):
    ZAKO_ROWS = (("zako_nando_hp", "Health", 0, "HP"), ("zako_nando_at", "Attack", 1, "attacks"),
                 ("zako_nando_etc", "Toughness", 2, "takes damage"))

    def __init__(self, parent, editor):
        super().__init__(parent, editor)
        self.sf = ScrollFrame(self)
        self.sf.pack(fill="both", expand=True)
        self.body = ttk.Frame(self.sf.inner, padding=(12, 10))
        self.body.pack(fill="both", expand=True)
        self.body.columnconfigure(0, weight=1, uniform="m")
        self.body.columnconfigure(1, weight=1, uniform="m")
        ttk.Label(self.body, text="Large monsters", style="H2.TLabel").grid(row=0, column=0, sticky="w", padx=6)
        self.cards = [MonsterCard(self.body, self, i) for i in range(MON_SLOTS)]
        self.add_btn = ttk.Button(self.body, text="+  Add a large monster", command=self._add)
        self.order = Section(self.body, "How the monsters arrive", H.ARRIVAL_TIP)
        og = self.order.body
        self.arrive = tk.IntVar(value=0)
        self.arrive_box = ttk.Frame(og, style="Card.TFrame")
        self.arrive_box.pack(anchor="w", fill="x")
        self.phase_lab = ttk.Label(og, style="Card.Accent.TLabel", wraplength=860, justify="left", text="")
        self.phase_lab.pack(anchor="w", pady=(8, 0))
        self.win_lab = ttk.Label(og, style="Card.TLabel", wraplength=860, justify="left", text="")
        self.win_lab.pack(anchor="w", pady=(4, 0))
        self.arrive_note = ttk.Label(og, style="Card.Muted.TLabel", wraplength=860, justify="left", text="")
        self.arrive_note.pack(anchor="w", pady=(4, 0))
        self._arrive_n = -1
        self._pat_lab = {}
        self.note = ttk.Label(self.body, style="Muted.TLabel", wraplength=900, justify="left", text=(
            "Tip: 'Copy from a quest...' copies a monster with every setting from another quest; it is "
            "the safest way to get a working monster. A monster the game does not allow on the "
            "quest's map is skipped and never appears (the card warns; the Monster pack can add the map)."))
        # small monsters
        self.small = Section(self.body, "Small monsters",
                             "The small monsters of the zone and how strong they are.")
        g = self.small.body
        left = ttk.Frame(g, style="Card.TFrame")
        left.pack(side="left", anchor="n", padx=(0, 40))
        right = ttk.Frame(g, style="Card.TFrame")
        right.pack(side="left", anchor="n")
        self.spawn_list = SpawnList(left, self)
        self.spawn_list.pack(anchor="w")
        self.zako = {}
        if self.dev:
            ttk.Label(left, text="Main species (developer mode)", style="Card.Muted.TLabel").pack(anchor="w", pady=(8, 2))
            for r, field in enumerate(("main_zako1", "main_zako2"), start=1):
                row = ttk.Frame(left, style="Card.TFrame")
                row.pack(anchor="w")
                ttk.Label(row, text=f"Species {r}", style="Card.TLabel").pack(side="left")
                b = IconButton(row, lambda f=field: self._pick_zako(f), width=22)
                b.pack(side="left", padx=6, pady=2)
                info(row, H.tip(field), "Card.").pack(side="left")
                self.zako[field] = b
        ttk.Label(right, text="Strength of all small monsters", style="Card.Muted.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 4))
        self.zako_lab = {}
        for r, (field, label, _c, _w) in enumerate(self.ZAKO_ROWS, start=1):
            self.field(right, r, label, field, tip=H.tip("zako_rows") + "\n" + H.common(field), width=6)
            lab = ttk.Label(right, text="", style="Card.Muted.TLabel")
            lab.grid(row=r, column=3, sticky="w")
            self.zako_lab[field] = lab
            self.hooks[field] = self._zako_text

    def load(self, q):
        mons = q.monsters
        used = [i for i, m in enumerate(mons) if m["Type"]]
        for c in self.cards:
            c.grid_forget()
        self.add_btn.grid_forget()
        n = 0
        for i in used:
            self.cards[i].grid(row=1 + n // 2, column=n % 2, sticky="nsew", padx=6, pady=6)
            self.cards[i].load(mons[i], n + 1 if len(used) > 1 else None)
            n += 1
        if len(used) < MON_SLOTS:
            self.add_btn.grid(row=1 + n // 2, column=n % 2, sticky="nw", padx=6, pady=6)
        self._show_arrival(q)
        if len(used) >= 2:
            self.order.grid(row=9, column=0, columnspan=2, sticky="nsew", padx=6, pady=(8, 0))
        else:
            self.order.grid_forget()
        self.note.grid(row=10, column=0, columnspan=2, sticky="w", padx=6, pady=(4, 12))
        self.small.grid(row=11, column=0, columnspan=2, sticky="nsew", padx=6)
        self.load_bound(q)
        self.spawn_list.load(q)
        for field, b in self.zako.items():
            em = q.get(field)
            b.show(self.app.icons.monster(em, 27) if em else self.app.icons.blank(27),
                   (G.mon_name(em) if em else "(none)") + (f"  em{em:03d}" if self.dev and em else ""))
        self._zako_text()

    @property
    def n_large(self) -> int:
        return len(waves.used_slots(self.q)) if self.q is not None else 0

    def _show_arrival(self, q):
        """Radio buttons for the arrival patterns that exist for this number of monsters."""
        n = len(waves.used_slots(q))
        if n != self._arrive_n:
            self._arrive_n = n
            for w in self.arrive_box.winfo_children():
                w.destroy()
            self._pat_lab = {}
            for val, groups, label, game in waves.patterns_for(n):
                row = ttk.Frame(self.arrive_box, style="Card.TFrame")
                row.pack(anchor="w", fill="x", pady=2)
                top = ttk.Frame(row, style="Card.TFrame")
                top.pack(anchor="w")
                ttk.Radiobutton(top, text=label, value=val, variable=self.arrive, style="Card.TRadiobutton",
                                command=self._arrive).pack(side="left")
                if not game:
                    info(top, "The game's own quests do not use this pattern with this number of monsters. "
                              "It is the same mechanism, but it has not been seen in a game quest: please "
                              "test it in the game.", "Card.").pack(side="left", padx=4)
                lab = ttk.Label(row, text="", style="Card.Muted.TLabel", wraplength=820, justify="left")
                lab.pack(anchor="w", padx=(24, 0))
                self._pat_lab[val] = (lab, groups)
        for val, (lab, groups) in self._pat_lab.items():
            lab.configure(text=waves.pattern_win(q, groups) if n > 1 else "")
        groups = waves.groups_of(q)
        if groups is None:
            self.arrive.set(-1)
            self.phase_lab.configure(text=f"Arrival pattern {q.get('start_param')}: not a pattern this editor "
                                          "knows for this number of monsters (kept as it is).")
        else:
            self.arrive.set(q.get("start_param") if n > 1 else 0)
            self.phase_lab.configure(text="In the game:  " + waves.wave_text(q, groups))
        self.win_lab.configure(text=waves.win_text(q))
        self.arrive_note.configure(text=H.ARRIVAL_NOTE if n > 1 else "")

    def _structural(self, change):
        """Run a change of the monster list; the arrival pattern stays valid and the objectives keep
        following the monsters if they did before."""
        q = self.q
        synced = waves.in_sync(q)
        change(q)
        waves.after_change(q, synced)
        self.editor.reload_tabs()
        self.editor.changed()

    def _arrive(self):
        q = self.q
        if q is None or self.loading:
            return
        val = self.arrive.get()
        if val < 0:
            return
        waves.set_pattern(q, val)
        waves.sync_objectives(q)
        self.editor.reload_tabs()
        self.editor.changed()

    def shift(self, slot, d):
        q = self.q
        if q is None:
            return
        j = slot + d
        used = [i for i, m in enumerate(q.monsters) if m["Type"]]
        if j not in used:
            return

        def swap(qq):
            a, b = dict(qq.monsters[slot]), dict(qq.monsters[j])
            qq.set_monster_all(slot, b)
            qq.set_monster_all(j, a)
        self._structural(swap)

    def _zako_text(self):
        if self.q is None:
            return
        for field, _l, col, what in self.ZAKO_ROWS:
            self.zako_lab[field].configure(text=mult_text(self.q.get(field), col, what))

    def _pick_zako(self, field):
        v = picker.pick_monster(self.app, self.q.get(field) or None, title="Small monster species",
                                allow_none=True, small_first=True)
        if v is not None:
            self.q.set(field, v)
            self.do_load(self.q)
            self.editor.changed()

    def _free_slot(self):
        for i, m in enumerate(self.q.monsters):
            if not m["Type"]:
                return i
        return None

    def _add(self):
        slot = self._free_slot()
        if slot is None:
            return
        em = picker.pick_monster(self.app, None, title="Add a large monster")
        if em is None:
            return
        self.set_species(slot, em)

    def set_species(self, slot, em):
        def change(q):
            before = q.monsters[slot]
            q.set_monster(slot, Type=em)
            if not before["Type"]:
                donor = next((m for i, m in enumerate(q.monsters) if m["Type"] and i != slot), None)
                block = H.default_monster_values(q)
                if donor:
                    block.update({k: donor[k] for k in block if k not in ("Starttype", "Settype")})
                q.set_monster(slot, **block)
            self._spread_starts(q)
        self._structural(change)

    def _spread_starts(self, q):
        """Copies of one species must not all start on the same spot: the game's own quests give
        each copy another start number (0, 1, 2...). A single monster keeps the game's default.
        Only start numbers the monster really has on this map are used."""
        pack, _inst = self.app.monster_pack()
        seen: dict = {}
        for i, m in enumerate(q.monsters):
            if not m["Type"]:
                continue
            ar = startpos.areas(m["Type"], q.get("map"), pack)
            n = len(ar) if ar else 1
            if m["Starttype"] >= n:
                q.set_monster(i, Starttype=0)
            k = seen.get(m["Type"], 0)
            if k > 0 and q.monsters[i]["Starttype"] == 0 and n > 1:
                q.set_monster(i, Starttype=k % n)
            seen[m["Type"]] = k + 1

    def remove(self, slot):
        q = self.q
        if not messagebox.askyesno("Remove monster", f"Remove {G.mon_name(q.monsters[slot]['Type'])} "
                                   "from the quest?", parent=self):
            return

        def change(qq):
            qq.clear_monster(slot)
            # keep monsters packed at the start (the game reads them in order)
            mons = [m for m in qq.monsters if m["Type"]]
            for i in range(MON_SLOTS):
                if i < len(mons):
                    qq.set_monster_all(i, mons[i])
                else:
                    qq.clear_monster(i)
            self._spread_starts(qq)
        self._structural(change)

    def copy_from(self, slot):
        opts = []
        for label, quest, cat in self.app.template_quests():
            for i, m in enumerate(quest.monsters):
                if m["Type"]:
                    em = m["Type"]
                    d = H.describe_stats(em, m["Nando_hp"], m["Nando_at"], m["Nando_etc"], quest.get("category"))
                    where = H.rank_label(quest) if cat == "Game quests" else cat
                    sub = f"{label}  ·  {where}  ·  {d.get('hp', '')}"
                    opts.append({"key": len(opts), "name": G.mon_name(em), "sub": sub, "cat": cat,
                                 "search": f"{G.mon_name(em)} {label} {where}",
                                 "icon": (lambda em=em: self.app.icons.monster(em, 54)),
                                 "_q": quest, "_i": i})
        if not opts:
            messagebox.showinfo("Copy a monster", "There is no quest to copy from yet.", parent=self)
            return
        cats = [c for c in ("In your game", "Library", "Game quests") if any(o["cat"] == c for o in opts)]
        res = picker._run(self.app, title="Copy a monster from a quest", entries=opts, tile=(420, 66),
                          icon_size=54, columns=2, categories=cats,
                          note="The monster is copied with all of its settings (strength, size, stamina...).")
        if res is None:
            return
        src = opts[res]
        def change(qq):
            qq.set_monster_all(slot, src["_q"].monsters[src["_i"]])
            qq.set_monster(slot, Starttype=0)         # start numbers belong to the other quest's map
            self._spread_starts(qq)
        self._structural(change)


# ================================================================ Supply Box
class SupplyTab(Tab):
    def __init__(self, parent, editor):
        super().__init__(parent, editor)
        body = self.scroll_body()
        body.columnconfigure(0, weight=3, uniform="s")
        body.columnconfigure(1, weight=2, uniform="s")
        s = Section(body, "Supply Box", H.tip("item_set_no"))
        s.grid(row=0, column=0, columnspan=1 if self.dev else 2, sticky="nsew", padx=(0, 6 if self.dev else 0))
        top = ttk.Frame(s.body, style="Card.TFrame")
        top.pack(fill="x")
        self.set_lab = ttk.Label(top, text="", style="Card.TLabel")
        self.set_lab.pack(side="left")
        ttk.Button(top, text="Choose another supply box...", command=self._pick_set).pack(side="right")
        tools = ttk.Frame(s.body, style="Card.TFrame")
        tools.pack(fill="x", pady=(6, 0))
        self.own_btn = ttk.Button(tools, text="Make my own box", command=self._make_custom)
        self.own_btn.pack(side="left")
        ttk.Button(tools, text="Fill from zone and rank...", command=self._auto).pack(side="left", padx=6)
        ttk.Button(tools, text="My supply boxes...", command=self.app.open_boxes).pack(side="left")
        info(tools, "Make my own box: copies this box into a box of yours, where you choose every item "
                    "(up to 40 different items, 99 of each) and give it a name. It needs the supply files of "
                    "the editor to be installed (see the note below). Fill from zone and rank: picks the game "
                    "box that the game's quests use on this zone at the chosen rank. My supply boxes: rename, "
                    "edit or delete your boxes, and remove their files from Citra.", "Card.").pack(side="left", padx=4)
        self.custom_bar = ttk.Frame(s.body, style="Card.TFrame")
        for text, cmd in (("Add an item...", self._add), ("Edit...", self._edit), ("Remove", self._remove),
                          ("Rename the box...", self._rename)):
            ttk.Button(self.custom_bar, text=text, command=cmd).pack(side="left", padx=(0, 4))
        self.tree = ttk.Treeview(s.body, columns=("qty",), height=14, style="Item.Treeview", selectmode="browse")
        self.tree.heading("#0", text="Item", anchor="w")
        self.tree.heading("qty", text="Qty")
        self.tree.column("#0", width=300)
        self.tree.column("qty", width=60, anchor="center")
        self.tree.pack(fill="both", expand=True, pady=(6, 0))
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit() if self.custom() else None)
        self.note = ttk.Label(s.body, style="Card.Muted.TLabel", wraplength=760, justify="left", text="")
        self.note.pack(anchor="w", pady=(8, 0))
        self.install_btn = ttk.Button(s.body, text="Install the supply files into Citra",
                                      command=self.app.install_supply_mod)

        if self.dev:
            s3 = Section(body, "Later deliveries",
                         "When the rest of the supply box arrives: on a timer, after 2 minutes, or once a "
                         "monster is hunted. Each (i) explains the values (from mh3u-quest-studio, checked "
                         "in the game on the Wii U version).")
            s3.grid(row=0, column=1, sticky="new", padx=(6, 0))
            for r, (field, label) in enumerate((("supp_set_no", "Timed delivery"),
                                                ("supp_time_flag", "Hunt delivery: monster"),
                                                ("supp_enemy_type", "Hunt delivery: how many"))):
                self.field(s3.body, r, label, field, tip=H.tip(field), width=7)
        self.hooks["item_set_no"] = self._fill_supply

    # ----- helpers
    def custom(self) -> bool:
        return self.q is not None and self.app.boxes.is_custom(self.q.get("item_set_no"))

    def load(self, q):
        self.load_bound(q)
        self._fill_supply()

    def _items(self):
        q = self.q
        no = q.get("item_set_no")
        if self.app.boxes.is_custom(no):
            return self.app.boxes.items(no)
        return G.SUPP_SETS.get(no)

    def _fill_supply(self):
        q = self.q
        no = q.get("item_set_no")
        custom = self.app.boxes.is_custom(no)
        if custom:
            self.set_lab.configure(text=f"{self.app.boxes.name(no)}" + (f" (number {no})" if self.dev else "")
                                   + ": items in the box at the start")
            self.custom_bar.pack(fill="x", pady=(6, 0), before=self.tree)
            self.own_btn.configure(text="Use a game box again...", command=self._pick_set)
            self.note.configure(text="This box exists only with the editor's supply files: save the quest, then "
                                "install them (Citra: button below; real 3DS: copy the output folder into "
                                "luma/titles/" + G.TITLE_ID + "/romfs). Without them the game opens the box it "
                                "normally has under this number. Every player of a multiplayer quest needs the "
                                "same files.")
            self.install_btn.pack(anchor="w", pady=(6, 0))
        else:
            self.set_lab.configure(text=f"Set {no}: items in the box at the start" if self.dev
                                   else "Items in the box at the start of the quest:")
            self.custom_bar.pack_forget()
            self.own_btn.configure(text="Make my own box", command=self._make_custom)
            self.note.configure(text="")
            self.install_btn.pack_forget()
        self.tree.delete(*self.tree.get_children())
        items = self._items()
        if items is None:
            self.tree.insert("", "end", text="  (this set does not exist in the game)", values=("",))
            return
        if custom:
            rows = list(items)
        else:
            merged = {}
            for iid, qty in items:
                merged[iid] = merged.get(iid, 0) + qty
            rows = list(merged.items())
        if not rows:
            self.tree.insert("", "end", text="  (empty)", values=("",))
        for i, (iid, qty) in enumerate(rows):
            name = G.item_name(iid) + (f"  #{iid}" if self.dev else "")
            self.tree.insert("", "end", iid=str(i), text="  " + name, image=self.app.icons.item(iid), values=(qty,))

    def _set_number(self, new):
        """Point the quest at another box. Your boxes are kept until you delete them yourself
        ('My supply boxes...'), so a box can be named, reused and removed from Citra properly."""
        self.q.set("item_set_no", new)

    def _pick_set(self):
        v = picker.pick_supply(self.app, self.q.get("item_set_no"))
        if v is not None:
            self._set_number(v)
            self.do_load(self.q)
            self.editor.changed()

    def _make_custom(self, ask_name=True):
        q = self.q
        if q is None:
            return
        no = self.app.boxes.free_number(self.app.supply_in_use())
        if no is None:
            messagebox.showinfo("Supply box", "There is room for 10 boxes of your own and they are all taken. "
                                "Open 'My supply boxes...' and delete one you do not need, or give a quest a "
                                "game box again.", parent=self)
            return
        items = [(i, min(99, n)) for i, n in (self._items() or [])]
        merged = {}
        for i, n in items:
            merged[i] = min(99, merged.get(i, 0) + n)
        try:
            self.app.boxes.set_items(no, list(merged.items())[:40])
        except ValueError as exc:
            messagebox.showerror("Supply box", str(exc), parent=self)
            return
        self._set_number(no)
        if ask_name:
            self._rename(first=True)
        self.do_load(q)
        self.editor.changed()

    def _rename(self, first=False):
        no = self.q.get("item_set_no")
        if not self.app.boxes.is_custom(no):
            return
        cur = self.app.boxes.name(no)
        while True:
            name = simpledialog.askstring("Name of the box", "Name of this supply box (you will see it in the "
                                          "list of supply boxes):", initialvalue=cur, parent=self)
            if name is None:
                return
            try:
                self.app.boxes.set_name(no, name)
                break
            except supp.SuppError as exc:
                messagebox.showerror("Supply box", str(exc), parent=self)
                cur = name
        if not first:
            self._fill_supply()

    def _write_box(self, items, select=None):
        no = self.q.get("item_set_no")
        try:
            self.app.boxes.set_items(no, items)
        except ValueError as exc:
            messagebox.showerror("Supply box", str(exc), parent=self)
            return
        self._fill_supply()
        if select is not None and self.tree.exists(str(select)):
            self.tree.selection_set(str(select))
        self.editor.changed()

    def _sel(self):
        s = self.tree.selection()
        return int(s[0]) if s and s[0].isdigit() else None

    def _add(self):
        items = self.app.boxes.items(self.q.get("item_set_no"))
        if len(items) >= 40:
            messagebox.showinfo("Supply box", "A box holds at most 40 different items.", parent=self)
            return
        dlg = RewardDialog(self.app, with_chance=False, title="Item for the supply box")
        self.wait_window(dlg)
        if dlg.result:
            items.append(dlg.result)
            self._write_box(items, len(items) - 1)

    def _edit(self):
        i = self._sel()
        if i is None:
            return
        items = self.app.boxes.items(self.q.get("item_set_no"))
        dlg = RewardDialog(self.app, items[i][0], items[i][1], with_chance=False, title="Item for the supply box")
        self.wait_window(dlg)
        if dlg.result:
            items[i] = dlg.result
            self._write_box(items, i)

    def _remove(self):
        i = self._sel()
        if i is not None:
            items = self.app.boxes.items(self.q.get("item_set_no"))
            del items[i]
            self._write_box(items)

    def _auto(self):
        q = self.q
        if q is None:
            return
        pool = ask_rank(self.app, "Supply box", "Choose the supply box from the game's own quests on "
                        f"{G.map_name(q.get('map'))}.", q.get("star"),
                        lambda p: (autofill.supply_box(q.get("map"), p) or (None, ""))[1])
        if pool is None:
            return
        res = autofill.supply_box(q.get("map"), pool)
        if res:
            vals = dict(res[0])
            self._set_number(vals.pop("item_set_no"))
            for f, v in vals.items():
                q.set(f, v)
            self.do_load(q)
            self.editor.changed()


class BoxItemsDialog(tk.Toplevel):
    """Edit the items of one of your supply boxes (not tied to a quest)."""

    def __init__(self, app, no):
        super().__init__(app)
        self.withdraw()
        self.app, self.no = app, no
        self.items = app.boxes.items(no)
        self.title(f"Items of '{app.boxes.name(no)}'")
        self.transient(app)
        self.configure(background=theme.color("bg"))
        f = ttk.Frame(self, padding=14)
        f.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(f, columns=("qty",), height=14, style="Item.Treeview", selectmode="browse")
        self.tree.heading("#0", text="Item", anchor="w")
        self.tree.heading("qty", text="Qty")
        self.tree.column("#0", width=300)
        self.tree.column("qty", width=60, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(8, 0))
        for text, cmd in (("Add an item...", self._add), ("Edit...", self._edit), ("Remove", self._remove)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 4))
        self.count = ttk.Label(bar, text="", style="Muted.TLabel")
        self.count.pack(side="right")
        b = ttk.Frame(self, padding=(14, 0, 14, 14))
        b.pack(fill="x")
        ttk.Button(b, text="Save", style="Accent.TButton", command=self._ok).pack(side="right")
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right", padx=6)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.saved = False
        self._fill()
        center_on(self, app)
        self.deiconify()
        make_modal(self)

    def _fill(self, select=None):
        self.tree.delete(*self.tree.get_children())
        for i, (iid, qty) in enumerate(self.items):
            self.tree.insert("", "end", iid=str(i), text="  " + G.item_name(iid) + (f"  #{iid}" if self.app.dev_mode.get() else ""),
                             image=self.app.icons.item(iid), values=(qty,))
        if select is not None and self.tree.exists(str(select)):
            self.tree.selection_set(str(select))
        self.count.configure(text=f"{len(self.items)} / {supp.SLOTS} items")

    def _sel(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def _add(self):
        if len(self.items) >= supp.SLOTS:
            messagebox.showinfo("Supply box", f"A box holds at most {supp.SLOTS} different items.", parent=self)
            return
        dlg = RewardDialog(self.app, with_chance=False, title="Item for the supply box")
        self.wait_window(dlg)
        if dlg.result:
            self.items.append(dlg.result)
            self._fill(len(self.items) - 1)

    def _edit(self):
        i = self._sel()
        if i is None:
            return
        dlg = RewardDialog(self.app, self.items[i][0], self.items[i][1], with_chance=False,
                           title="Item for the supply box")
        self.wait_window(dlg)
        if dlg.result:
            self.items[i] = dlg.result
            self._fill(i)

    def _remove(self):
        i = self._sel()
        if i is not None:
            del self.items[i]
            self._fill()

    def _ok(self):
        try:
            self.app.boxes.set_items(self.no, self.items)
        except supp.SuppError as exc:
            messagebox.showerror("Supply box", str(exc), parent=self)
            return
        self.saved = True
        self.destroy()


class BoxManager(tk.Toplevel):
    """Your own supply boxes: name, contents, which quests use them, and the supply files that are
    installed in Citra (the files can be removed from here)."""

    def __init__(self, app):
        super().__init__(app)
        self.withdraw()
        self.app = app
        self.title("My supply boxes")
        self.transient(app)
        self.configure(background=theme.color("bg"))
        f = ttk.Frame(self, padding=16)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="My supply boxes", style="H2.TLabel").pack(anchor="w")
        ttk.Label(f, style="Muted.TLabel", wraplength=720, justify="left", text=(
            "A box of your own is a small file that the game reads when a quest opens its supply box. The editor "
            "can keep 10 boxes. Quests of yours can share a box. The files are installed into Citra with the "
            "button below; here you can also take them out again.")).pack(anchor="w", pady=(2, 8))
        cols = ("items", "quests", "citra")
        self.tree = ttk.Treeview(f, columns=cols, height=10, selectmode="browse", style="Item.Treeview")
        self.tree.heading("#0", text="Box", anchor="w")
        self.tree.heading("items", text="Items")
        self.tree.heading("quests", text="Quests using it")
        self.tree.heading("citra", text="In Citra")
        self.tree.column("#0", width=250)
        self.tree.column("items", width=60, anchor="center")
        self.tree.column("quests", width=120, anchor="center")
        self.tree.column("citra", width=200, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._detail())
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())
        self.detail = ttk.Label(f, text="", style="Muted.TLabel", wraplength=720, justify="left")
        self.detail.pack(anchor="w", pady=(6, 0))
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(10, 0))
        for text, cmd in (("Rename...", self._rename), ("Edit the items...", self._edit),
                          ("Delete the box", self._delete)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 4))
        bar2 = ttk.Frame(f)
        bar2.pack(fill="x", pady=(6, 0))
        ttk.Button(bar2, text="Install the supply files into Citra", command=self._install).pack(side="left")
        ttk.Button(bar2, text="Remove the selected file from Citra", command=self._remove_file).pack(side="left", padx=6)
        self.where = ttk.Label(f, text="", style="Muted.TLabel", wraplength=720, justify="left")
        self.where.pack(anchor="w", pady=(8, 0))
        ttk.Button(f, text="Close", command=self.destroy).pack(anchor="e", pady=(10, 0))
        self.bind("<Escape>", lambda _e: self.destroy())
        self.rows: dict[str, tuple] = {}
        self.fill()
        center_on(self, app)
        self.deiconify()
        make_modal(self)

    # ----------------------------------------------------------------- list
    def fill(self, keep=None):
        app = self.app
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        dests, files = app.citra_supply()
        self.where.configure(text=("Citra mod folder: " + str(dests[0]) if dests else
                                   "Citra's 'load' folder was not found: nothing can be installed or removed "
                                   "from here. For a real 3DS, the files are in the output folder next to the "
                                   "program (see the Supply Box tab)."))
        for no in app.boxes.numbers():
            items = app.boxes.items(no)
            users = app.supply_users(no)
            state = supp.file_state(files.get(no), items) if dests else "-"
            text = {"missing": "not installed", "same": "installed", "older": "installed (different content)",
                    "-": "-"}[state]
            if state == "missing" and not users:
                text = "not installed (no quest uses it)"
            name = app.boxes.name(no) + (f"   (number {no})" if app.dev_mode.get() else "")
            self.tree.insert("", "end", iid=f"b{no}", text="  " + name, values=(len(items), len(users), text),
                             image=app.icons.item(items[0][0], 2) if items else "")
            self.rows[f"b{no}"] = ("box", no, users)
        for no in sorted(set(files) - set(app.boxes.numbers())):
            self.tree.insert("", "end", iid=f"f{no}", text=f"  (a file in Citra that is no longer one of your boxes)",
                             values=("", "", f"installed: {supp.file_name(no)}"))
            self.rows[f"f{no}"] = ("file", no, [])
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)
        self._detail()

    def _current(self):
        sel = self.tree.selection()
        return (sel[0], *self.rows[sel[0]]) if sel and sel[0] in self.rows else None

    def _detail(self):
        cur = self._current()
        if cur is None:
            self.detail.configure(text="Select a box." if self.rows else "You have no box of your own yet. "
                                  "Make one in the Supply Box tab of a quest ('Make my own box').")
            return
        _iid, kind, no, users = cur
        if kind == "file":
            self.detail.configure(text=f"{supp.file_name(no)} sits in Citra but the editor does not know a box "
                                       "with this number. 'Remove the selected file from Citra' deletes it.")
            return
        items = self.app.boxes.items(no)
        names = [G.item_name(i) + (f" ×{q}" if q > 1 else "") for i, q in items[:8]]
        text = ", ".join(names) + (" ..." if len(items) > 8 else "") if items else "(empty)"
        if users:
            text += "\nUsed by: " + ", ".join(users[:6]) + (" ..." if len(users) > 6 else "")
        self.detail.configure(text=text)

    # ------------------------------------------------------------- actions
    def _rename(self):
        cur = self._current()
        if cur is None or cur[1] != "box":
            return
        iid, _k, no, _u = cur
        name = self.app.boxes.name(no)
        while True:
            name = simpledialog.askstring("Name of the box", "Name of this supply box:", initialvalue=name, parent=self)
            if name is None:
                return
            try:
                self.app.boxes.set_name(no, name)
                break
            except supp.SuppError as exc:
                messagebox.showerror("Supply box", str(exc), parent=self)
        self.fill(iid)

    def _edit(self):
        cur = self._current()
        if cur is None or cur[1] != "box":
            return
        dlg = BoxItemsDialog(self.app, cur[2])
        self.wait_window(dlg)
        if dlg.saved:
            self.app.set_status("Box saved. Install the supply files into Citra again to use the new items.")
        self.fill(cur[0])

    def _delete(self):
        cur = self._current()
        if cur is None or cur[1] != "box":
            return
        _iid, _k, no, users = cur
        app = self.app
        text = f"Delete '{app.boxes.name(no)}'?\n\nIts file is also removed from Citra if it is installed there."
        if users:
            text += ("\n\nThese quests of yours use it: " + ", ".join(users[:8]) + (" ..." if len(users) > 8 else "")
                     + f".\nThey will open the game's own box number {no} instead until you give them another.")
        if not messagebox.askyesno("Delete the box", text, parent=self):
            return
        done, errors = app.delete_box(no)
        if errors:
            messagebox.showwarning("Delete the box", "The box was deleted, but Citra's file could not be removed:\n"
                                   + "\n".join(errors), parent=self)
        app.set_status(f"Box deleted" + (f" and its file removed from Citra." if done else "."))
        self.fill()

    def _install(self):
        self.app.install_supply_mod()
        self.fill()

    def _remove_file(self):
        cur = self._current()
        if cur is None:
            return
        _iid, _k, no, _u = cur
        done, errors = self.app.remove_citra_supply([no])
        if errors:
            messagebox.showerror("Citra", "Could not remove:\n" + "\n".join(errors), parent=self)
        elif done:
            self.app.set_status(f"{supp.file_name(no)} removed from Citra: quests that use box {no} open the game's own box.")
        else:
            messagebox.showinfo("Citra", "That file is not installed in Citra.", parent=self)
        self.fill(cur[0])


# ==================================================================== Rewards
class RewardDialog(tk.Toplevel):
    def __init__(self, app, item=0, qty=1, chance=10, with_chance=True, title="Reward"):
        super().__init__(app)
        self.with_chance = with_chance
        self.withdraw()
        self.app = app
        self.title(title)
        self.transient(app)
        self.configure(background=theme.color("bg"))
        self.result = None
        self.item = item
        f = ttk.Frame(self, padding=14)
        f.pack(fill="both")
        ttk.Label(f, text="Item").grid(row=0, column=0, sticky="w", pady=4)
        self.btn = IconButton(f, self._pick, width=26)
        self.btn.grid(row=0, column=1, sticky="w", padx=6)
        self.qty = tk.StringVar(value=str(qty))
        self.chance = tk.StringVar(value=str(chance))
        ttk.Label(f, text="Quantity").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Spinbox(f, from_=1, to=99, width=6, textvariable=self.qty).grid(row=1, column=1, sticky="w", padx=6)
        if with_chance:
            ttk.Label(f, text="Chance (%)").grid(row=2, column=0, sticky="w", pady=4)
            ttk.Spinbox(f, from_=1, to=100, width=6, textvariable=self.chance).grid(row=2, column=1, sticky="w", padx=6)
        b = ttk.Frame(self, padding=(14, 0, 14, 14))
        b.pack(fill="x")
        ttk.Button(b, text="OK", style="Accent.TButton", command=self._ok).pack(side="right")
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right", padx=6)
        self._show()
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        center_on(self, app)
        self.deiconify()
        make_modal(self)
        if not item:
            self.after(50, self._pick)

    def _show(self):
        self.btn.show(self.app.icons.item(self.item, 2) if self.item else None,
                      G.item_name(self.item) if self.item else "Choose an item...")

    def _pick(self):
        v = picker.pick_item(self.app, self.item or None)
        if v is not None:
            self.item = v
            self._show()

    def _ok(self):
        try:
            qty, chance = parse_int(self.qty.get()), parse_int(self.chance.get())
        except ValueError:
            messagebox.showerror("Reward", "Quantity and chance must be numbers.", parent=self)
            return
        top = 255 if self.with_chance else 99
        if not self.item or not (1 <= qty <= top and 0 <= chance <= 255):
            messagebox.showerror("Item", f"Choose an item; the quantity goes from 1 to {top}.", parent=self)
            return
        self.result = (self.item, qty, chance) if self.with_chance else (self.item, qty)
        self.destroy()


class RewardsTab(Tab):
    def __init__(self, parent, editor):
        super().__init__(parent, editor)
        body = ttk.Frame(self, padding=(12, 10))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self.trees, self.totals = {}, {}
        auto = ttk.Frame(body)
        auto.grid(row=1, column=0, columnspan=2, sticky="w", padx=6, pady=(8, 0))
        ttk.Button(auto, text="Fill from the quest's monsters and rank...", command=self._auto).pack(side="left")
        info(auto, "Builds table A from the game's own quests: the materials of each large monster of this "
                   "quest, plus the other items the game gives at that rank and zone (spheres, charms, "
                   "ores, bones, bugs...). The dialog says what it is based on. Everything stays editable.").pack(
            side="left", padx=4)
        for table in (1, 2):
            s = Section(body, f"Reward table {'AB'[table - 1]}", H.tip("rewards"))
            s.grid(row=0, column=table - 1, sticky="nsew", padx=6)
            tree = ttk.Treeview(s.body, columns=("qty", "chance"), height=12, selectmode="browse",
                                style="Item.Treeview")
            tree.heading("#0", text="Item", anchor="w")
            tree.heading("qty", text="Qty")
            tree.heading("chance", text="Chance")
            tree.column("#0", width=250)
            tree.column("qty", width=50, anchor="center")
            tree.column("chance", width=70, anchor="center")
            tree.pack(fill="both", expand=True)
            tree.bind("<Double-Button-1>", lambda _e, t=table: self._edit(t))
            tree.tag_configure("odd", background=theme.color("stripe"))
            bar = ttk.Frame(s.body, style="Card.TFrame")
            bar.pack(fill="x", pady=(6, 0))
            for text, cmd in (("Add...", self._add), ("Edit...", self._edit), ("Remove", self._remove),
                              (UP, lambda t: self._move(t, -1)), (DOWN, lambda t: self._move(t, 1))):
                ttk.Button(bar, text=text, command=lambda c=cmd, t=table: c(t),
                           width=3 if len(text) == 1 else None).pack(side="left", padx=(0, 4))
            tot = ttk.Label(bar, text="", style="Card.Muted.TLabel")
            tot.pack(side="right")
            self.trees[table], self.totals[table] = tree, tot

    def _rows(self, t):
        return list(self.q.reward1 if t == 1 else self.q.reward2)

    def _auto(self):
        q = self.q
        if q is None:
            return
        if not any(m["Type"] for m in q.monsters):
            messagebox.showinfo("Quest rewards", "Add a large monster first: the rewards are built from "
                                "the monsters of the quest.", parent=self)
            return
        pool = ask_rank(self.app, "Quest rewards", "Fill the reward tables with the materials of EVERY large "
                        "monster of this quest, plus the other items (armor spheres, charms, ores, bones, "
                        "bugs...) that the game's quests of that rank give.", q.get("star"),
                        lambda p: (autofill.reward_plan(q, p) or (0, 0, ""))[2])
        if pool is None:
            return
        plan = autofill.reward_plan(q, pool)
        if not plan:
            return
        if any(self._rows(t) for t in (1, 2)) and not messagebox.askyesno(
                "Quest rewards", "Replace the current reward tables?", parent=self):
            return
        autofill.apply_reward_plan(q, plan)
        self.do_load(q)
        self.editor.changed()

    def load(self, q):
        for t in (1, 2):
            self._fill(t, self._rows(t))

    def _fill(self, t, rows):
        tree = self.trees[t]
        tree.delete(*tree.get_children())
        for i, (iid, qty, ch) in enumerate(rows):
            name = G.item_name(iid) + (f"  #{iid}" if self.dev else "")
            tree.insert("", "end", iid=str(i), text="  " + name, image=self.app.icons.item(iid),
                        values=(qty, f"{ch} %"), tags=("odd",) if i % 2 else ())
        total = sum(r[2] for r in rows)
        self.totals[t].configure(text=f"{len(rows)}/32 items · {total} %")

    def _write(self, t, rows, select=None):
        try:
            self.q.set_reward_table(t, rows)
        except QuestFormatError as exc:
            messagebox.showerror("Rewards", str(exc), parent=self)
            return
        self._fill(t, rows)
        if select is not None and self.trees[t].exists(str(select)):
            self.trees[t].selection_set(str(select))
        self.editor.changed()

    def _sel(self, t):
        s = self.trees[t].selection()
        return int(s[0]) if s else None

    def _add(self, t):
        rows = self._rows(t)
        if len(rows) >= 32:
            messagebox.showinfo("Rewards", "A reward table holds at most 32 items.", parent=self)
            return
        dlg = RewardDialog(self.app)
        self.wait_window(dlg)
        if dlg.result:
            self._write(t, rows + [dlg.result], len(rows))

    def _edit(self, t):
        i = self._sel(t)
        if i is None:
            return
        rows = self._rows(t)
        dlg = RewardDialog(self.app, *rows[i])
        self.wait_window(dlg)
        if dlg.result:
            rows[i] = dlg.result
            self._write(t, rows, i)

    def _remove(self, t):
        i = self._sel(t)
        if i is not None:
            rows = self._rows(t)
            del rows[i]
            self._write(t, rows)

    def _move(self, t, d):
        i = self._sel(t)
        rows = self._rows(t)
        if i is None or not 0 <= i + d < len(rows):
            return
        rows[i], rows[i + d] = rows[i + d], rows[i]
        self._write(t, rows, i + d)


# ======================================================================= Text
class TextTab(Tab):
    FIELDS = (("name", "Quest name", 1), ("objective", "Objective text", 2), ("sub_objective", "Sub-objective", 2),
              ("failure", "Failure conditions", 2), ("client", "Client", 2), ("description", "Description", 6))

    def __init__(self, parent, editor):
        super().__init__(parent, editor)
        self.lang = 0
        body = self.scroll_body()
        top = ttk.Frame(body)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Language").pack(side="left")
        self.langs = ttk.Combobox(top, state="readonly", width=12, values=[LANG_NAMES[c] for c in LANGS])
        self.langs.current(0)
        self.langs.pack(side="left", padx=6)
        self.langs.bind("<<ComboboxSelected>>", self._lang)
        ttk.Button(top, text="Copy this language to the 4 others", command=self._copy_all).pack(side="left", padx=6)
        info(top, "The game stores every text in English, French, German, Italian and Spanish; "
                  "the console language decides which one you see.").pack(side="left")
        s = Section(body, "Texts")
        s.pack(fill="both", expand=True)
        g = s.body
        g.columnconfigure(1, weight=1)
        self.w = {}
        for r, (field, label, h) in enumerate(self.FIELDS):
            ttk.Label(g, text=label, style="Card.TLabel").grid(row=r, column=0, sticky="nw", padx=(0, 10), pady=4)
            if h == 1:
                var = tk.StringVar()
                e = ttk.Entry(g, textvariable=var)
                e.grid(row=r, column=1, sticky="ew", pady=4)
                var.trace_add("write", lambda *_a, f=field: self._commit(f))
                self.w[field] = ("e", e, var)
            else:
                t = tk.Text(g, height=h, wrap="word", undo=True, width=60)
                theme.style_text(t)
                t.grid(row=r, column=1, sticky="ew", pady=4)
                for seq in ("<KeyRelease>", "<FocusOut>"):
                    t.bind(seq, lambda _e, f=field: self._commit(f))
                self.w[field] = ("t", t, None)

    def load(self, q):
        for field, (kind, w, var) in self.w.items():
            text = q.get_text(field, self.lang)
            if kind == "e":
                var.set(text)
            else:
                w.delete("1.0", "end")
                w.insert("1.0", text.replace("\r\n", "\n"))

    def _read(self, field):
        kind, w, var = self.w[field]
        return var.get() if kind == "e" else w.get("1.0", "end-1c").replace("\n", "\r\n")

    def _commit(self, field):
        if self.loading or self.q is None:
            return
        text = self._read(field)
        if text.encode("utf-8") != self.q.get_raw_text(field, self.lang):
            self.q.set_text(field, text, langs=[self.lang])
            self.editor.changed()

    def _lang(self, _e=None):
        self.lang = self.langs.current()
        if self.q is not None:
            self.do_load(self.q)

    def _copy_all(self):
        if self.q is None:
            return
        if not messagebox.askyesno("Copy texts", f"Replace the other languages with the "
                                   f"{LANG_NAMES[LANGS[self.lang]]} texts?", parent=self):
            return
        others = [i for i in range(len(LANGS)) if i != self.lang]
        for field, _l, _h in self.FIELDS:
            self.q.set_text(field, self.q.get_raw_text(field, self.lang), langs=others)
        self.editor.changed()


# =================================================================== Advanced
class AdvancedTab(Tab):
    """Developer mode only: category bits and every raw field."""

    def __init__(self, parent, editor):
        super().__init__(parent, editor)
        body = ttk.Frame(self, padding=(12, 10))
        body.pack(fill="both", expand=True)
        s = Section(body, "Category flags", H.tip("category"))
        s.pack(fill="x")
        self.bits = []
        names = {b["bit"]: b["name"] for b in G.FLAG_BITS if b.get("name")}
        for bit in range(32):
            var = tk.BooleanVar()
            ttk.Checkbutton(s.body, text=f"{bit}" + (f" {names[bit]}" if bit in names else ""), variable=var,
                            style="Card.TCheckbutton", command=self._bits).grid(
                row=bit % 8, column=bit // 8, sticky="w", padx=6)
            self.bits.append(var)
        row = ttk.Frame(s.body, style="Card.TFrame")
        row.grid(row=9, column=0, columnspan=4, sticky="w", pady=6)
        ttk.Label(row, text="64-bit value (hex)", style="Card.TLabel").pack(side="left")
        self.hex = tk.StringVar()
        ttk.Entry(row, textvariable=self.hex, width=20).pack(side="left", padx=6)
        ttk.Button(row, text="Apply", command=self._apply).pack(side="left")
        s2 = Section(body, "Every numeric field (double-click to edit)")
        s2.pack(fill="both", expand=True, pady=(10, 0))
        self.tree = ttk.Treeview(s2.body, columns=("v", "hex"), height=10, style="Small.Treeview")
        self.tree.heading("#0", text="Field", anchor="w")
        self.tree.heading("v", text="Value", anchor="w")
        self.tree.heading("hex", text="Hex", anchor="w")
        self.tree.column("#0", width=220)
        sb = ttk.Scrollbar(s2.body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<Double-Button-1>", self._edit)

    def load(self, q):
        cat = q.get("category")
        for bit, var in enumerate(self.bits):
            var.set(bool(cat >> bit & 1))
        self.hex.set(f"{cat:016X}")
        self.tree.delete(*self.tree.get_children())
        for name in q.scalar_names:
            v = q.get(name)
            self.tree.insert("", "end", iid=name, text=name, values=(v, f"0x{v & ((1 << 64) - 1):X}"))
        self.tree.insert("", "end", iid="_tail", text="(hidden tail data)", values=(f"{len(q.tail)} bytes", "kept as is"))

    def _bits(self):
        if self.loading:
            return
        cat = self.q.get("category") & ~0xFFFFFFFF
        for bit, var in enumerate(self.bits):
            if var.get():
                cat |= 1 << bit
        self.q.set("category", cat)
        self.do_load(self.q)
        self.editor.changed()

    def _apply(self):
        try:
            self.q.set("category", int(self.hex.get().strip(), 16))
        except (ValueError, QuestFormatError):
            messagebox.showerror("Category", "Enter a hexadecimal value of up to 16 digits.", parent=self)
            return
        self.do_load(self.q)
        self.editor.changed()

    def _edit(self, _e=None):
        sel = self.tree.selection()
        if not sel or sel[0] == "_tail":
            return
        name = sel[0]
        lo, hi = self.q.scalar_range(name)
        v = simpledialog.askinteger("Edit field", f"{name} ({lo} .. {hi})", initialvalue=self.q.get(name),
                                    minvalue=lo, maxvalue=hi, parent=self)
        if v is not None:
            self.q.set(name, v)
            self.editor.reload_tabs()
            self.editor.changed()


# ===================================================================== page
class EditorPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.quest = None
        self.key = None
        self.snapshot = None
        bar = ttk.Frame(self, style="Panel.TFrame", padding=(8, 6))
        bar.pack(fill="x")
        self.back = ttk.Button(bar, text="‹  Back", command=app.show_home)
        self.back.pack(side="left")
        self.where = ttk.Label(bar, text="", style="Panel.Muted.TLabel")
        self.where.pack(side="left", padx=10)
        ttk.Button(bar, text="Save  (Ctrl+S)", style="Accent.TButton", command=app.save).pack(side="right")
        self.undo_btn = ttk.Button(bar, text="Undo changes", command=self.undo)
        self.undo_btn.pack(side="right", padx=6)
        Tooltip(self.undo_btn, "Puts the quest back as it was when you opened it (or last saved it).")
        self.checks = ttk.Button(bar, text="", command=self.show_checks)
        self.checks.pack(side="right", padx=(0, 6))
        self.check_dot = ttk.Frame(bar, style="Panel.TFrame")
        self.check_dot.pack(side="right")
        Tooltip(self.checks, "Checks for mistakes that can stop the quest from loading. Click for details.")

        card = ttk.Frame(self, style="Box.TFrame", padding=(12, 8))
        card.pack(fill="x", padx=10, pady=(8, 4))
        self.mon_icons = ttk.Frame(card, style="Card.TFrame")
        self.mon_icons.pack(side="left")
        txt = ttk.Frame(card, style="Card.TFrame")
        txt.pack(side="left", padx=12, fill="x", expand=True)
        self.title_lab = ttk.Label(txt, text="", style="Card.Title.TLabel")
        self.title_lab.pack(anchor="w")
        self.sub_lab = ttk.Label(txt, text="", style="Card.Muted.TLabel")
        self.sub_lab.pack(anchor="w")
        self.obj_lab = ttk.Label(txt, text="", style="Card.Accent.TLabel", wraplength=760, justify="left")
        self.obj_lab.pack(anchor="w", pady=(2, 0))
        self.map_lab = ttk.Label(card, style="Card.TLabel")
        self.map_lab.pack(side="right", padx=(10, 0))
        right = ttk.Frame(card, style="Card.TFrame")
        right.pack(side="right", anchor="n")
        self.star_lab = ttk.Label(right, text="", style="Card.Gold.TLabel")
        self.star_lab.pack(anchor="e")
        self.rank_lab = ttk.Label(right, text="", style="Card.Muted.TLabel")
        self.rank_lab.pack(anchor="e")
        self.tier_lab = ttk.Label(right, text="", style="Card.Accent.TLabel")
        self.tier_lab.pack(anchor="e")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self.nb.bind("<<NotebookTabChanged>>",
                     lambda _e: self.after(60, lambda: getattr(self.app, "finder", None) and self.app.finder.refresh()))
        self.build_tabs()

    def build_tabs(self):
        for t in getattr(self, "tabs", []):
            t.destroy()
        self.tabs = []
        spec = [("General", GeneralTab), ("Monsters", MonstersTab), ("Supply Box", SupplyTab),
                ("Rewards", RewardsTab), ("Text", TextTab)]
        if self.app.dev_mode.get():
            spec.append(("Advanced", AdvancedTab))
        for title, cls in spec:
            tab = cls(self.nb, self)
            self.nb.add(tab, text=title)
            self.tabs.append(tab)

    def open(self, key, quest, where, back="Back", keep_snapshot=False):
        if not keep_snapshot or self.snapshot is None or key != self.key:
            self.snapshot = quest.to_bytes()
        self.key, self.quest = key, quest
        self.back.configure(text=f"‹  {back}")
        self.where.configure(text=where)
        self.reload_tabs()
        if not keep_snapshot:
            self.nb.select(0)
        self.refresh_card()
        self.revalidate()

    def leave(self) -> bool:
        """Called before another page is shown. Edits stay in memory until saved."""
        return True

    def reload_tabs(self):
        for t in self.tabs:
            t.do_load(self.quest)

    def refresh_card(self):
        q = self.quest
        if q is None:
            return
        icons = self.app.icons
        for w in self.mon_icons.winfo_children():
            w.destroy()
        self._imgs = []
        mons = [m["Type"] for m in q.monsters if m["Type"]]
        for em in list(dict.fromkeys(mons))[:5]:
            img = icons.monster(em, 54)
            self._imgs.append(img)
            lab = ttk.Label(self.mon_icons, image=img, style="Card.TLabel")
            lab.pack(side="left", padx=1)
            Tooltip(lab, G.mon_name(em))
        if not mons:
            img = icons.quest(q, 54)
            self._imgs.append(img)
            ttk.Label(self.mon_icons, image=img, style="Card.TLabel").pack(side="left")
        self.title_lab.configure(text=q.get_text("name", 0) or "(untitled quest)")
        num = f"#{q.get('quest_no')}  ·  " if self.app.dev_mode.get() else ""
        self.sub_lab.configure(text=f"{num}{G.map_name(q.get('map'))}  ·  {q.get('time_min')} min  ·  "
                                    f"fee {q.get('contract'):,}z  ·  reward {q.get('reward_money'):,}z  ·  "
                                    f"{q.get('main_hrp'):,} HR points")
        self.obj_lab.configure(text=G.objectives_sentence(q))
        self.star_lab.configure(text=stars(q.get("star")))
        self.rank_lab.configure(text=H.rank_label(q))
        t = H.quest_tier(q)
        self.tier_lab.configure(text=f"Monsters: {tier_text(t)}" if t >= 0 else "",
                                style="Card.Danger.TLabel" if t == H.NIGHTMARE else "Card.Accent.TLabel")
        self._map_img = icons.map(q.get("map"), 64)
        self.map_lab.configure(image=self._map_img)

    def changed(self, refresh_title=True):
        if self.key is None:
            return
        self.app.on_quest_changed(self.key)
        self.refresh_card()
        self.revalidate()

    def undo(self):
        if self.quest is None or self.snapshot is None:
            return
        if self.quest.to_bytes() == self.snapshot:
            self.app.set_status("Nothing to undo: the quest is as it was when you opened it.")
            return
        if not messagebox.askyesno("Undo changes", "Put this quest back as it was when you opened it "
                                   "(or last saved it)?", parent=self):
            return
        self.quest.replace_bytes(self.snapshot)
        self.reload_tabs()
        self.changed()
        self.app.set_status("Changes undone. Save to write the quest back.")

    def issues(self):
        return self.app.validate(self.key, self.quest)

    def revalidate(self):
        found = self.issues()
        lvl = worst(found)
        n_err = sum(1 for i in found if i.level == "error")
        n_warn = sum(1 for i in found if i.level == "warning")
        for w in self.check_dot.winfo_children():
            w.destroy()
        kind = "ok" if lvl in (None, "info") else ("error" if n_err else "warn")
        StatusDot(self.check_dot, kind, "panel").pack()
        if lvl in (None, "info"):
            self.checks.configure(text="Checks: no problem found")
        else:
            parts = []
            if n_err:
                parts.append(f"{n_err} error{'s' if n_err > 1 else ''}")
            if n_warn:
                parts.append(f"{n_warn} warning{'s' if n_warn > 1 else ''}")
            self.checks.configure(text="Checks: " + ", ".join(parts))

    def show_checks(self):
        found = self.issues()
        win = tk.Toplevel(self)
        win.withdraw()
        win.title("Quest checks")
        win.configure(background=theme.color("bg"))
        win.transient(self.app)
        f = ttk.Frame(win, padding=14)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Quest checks", style="H2.TLabel").pack(anchor="w", pady=(0, 6))
        if not found:
            ttk.Label(f, text="No problem found.", style="Ok.TLabel").pack(anchor="w")
        for i in found:
            style = {"error": "Danger.TLabel", "warning": "Warn.TLabel"}.get(i.level, "Muted.TLabel")
            ttk.Label(f, text=f"{i.level.capitalize()}:  {i.text}", style=style, wraplength=560,
                      justify="left").pack(anchor="w", pady=2)
        ttk.Button(f, text="Close", command=win.destroy).pack(anchor="e", pady=(10, 0))
        win.bind("<Escape>", lambda _e: win.destroy())
        center_on(win, self.app)
        win.deiconify()
