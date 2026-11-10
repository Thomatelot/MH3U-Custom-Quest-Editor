"""Screenshots of the main screens in one language (needs a display, e.g. xvfb-run).

    python tests/gui_lang.py <packs_copy_dir> <romfs_dir> <shots_dir> <theme> <en|fr>

Works on a COPY of the quest files; nothing is saved. Checks that the main screens open
without errors in the chosen language and lists the visible texts that stayed in English.
"""
from __future__ import annotations

import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PACKS, ROMFS, SHOTS, THEME, LANG = sys.argv[1:6]
SHOTS = Path(SHOTS)
SHOTS.mkdir(parents=True, exist_ok=True)

from mhqe import project  # noqa: E402

cfg = project.Settings()
for k, v in (("setup_done", True), ("theme", THEME), ("language", LANG), ("pack_dir", PACKS),
             ("romfs", ROMFS), ("dev_mode", False)):
    cfg.set(k, v)

from tkinter import messagebox  # noqa: E402

from mhqe import app as A, i18n, picker  # noqa: E402

errors: list[str] = []
messagebox.showerror = lambda *a, **k: errors.append(f"ERROR dialog: {a[1] if len(a) > 1 else a}")
app = A.App()


def settle(t=0.3):
    end = time.time() + t
    while time.time() < end:
        app.update()
        time.sleep(0.02)


def shot(name, window=None):
    settle(0.4)
    wid = app.wm_frame() if window is None else str(window.winfo_id())
    subprocess.run(["import", "-window", wid, str(SHOTS / f"{LANG}_{THEME}_{name}.png")], check=False)


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


def collect():
    pass


def grab_toplevel(name, close=True):
    tops = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel) and w.winfo_ismapped()]
    if tops:
        shot(name, tops[-1])
        if close:
            tops[-1].destroy()


def run():
    app.geometry("1320x860+0+0")
    settle(0.8)
    shot("01_home")
    collect()
    src = app.sources["packs"]
    target = None
    for e in src.entries():
        q = src.get(e.key)
        if q is not None and any(m["Type"] for m in q.monsters):
            target = e.key
            break
    app.open_editor("packs", target)
    settle(0.6)
    for i, name in enumerate(("general", "monsters", "supply", "rewards", "text")):
        app.editor.nb.select(i)
        settle(0.4)
        shot(f"02_editor_{name}")
        collect()
    app.editor.nb.select(1)
    settle(0.3)
    card = app.editor.tabs[1].cards[0] if hasattr(app.editor.tabs[1], "cards") else None
    app.after(1200, lambda: grab_toplevel("03_start_dialog"))
    if card is not None:
        card._start()
    settle(0.5)
    app.after(1200, lambda: grab_toplevel("04_picker_monsters"))
    picker.pick_monster(app)
    settle(0.5)
    app.after(1500, lambda: grab_toplevel("05_picker_items"))
    picker.pick_item(app)
    settle(0.5)
    app.after(1200, lambda: grab_toplevel("06_settings"))
    app.open_settings()
    settle(0.5)
    from mhqe import arena, editor as E
    ch = next((e.key for e in src.entries() if src.get(e.key) is not None
               and arena.uses_gear(src.get(e.key).get("quest_no"))), None)
    if ch is not None:
        app.open_editor("packs", ch)
        settle(0.6)
        gear = next(t for t in app.editor.tabs if isinstance(t, E.GearTab))
        app.editor.nb.select(gear)
        settle(0.6)
        shot("08_challenge_gear")
        app.editor.nb.select(0)
        settle(0.4)
        shot("09_challenge_general")
    else:
        errors.append("ERROR no challenge quest found in pack 4")
    ds = next((e.key for e in src.entries() if src.get(e.key) is not None
               and src.get(e.key).get("map") == 6), None)
    if ds is not None:
        app.open_editor("packs", ds)
        settle(0.6)
        q = app.editor.quest
        q.set_objective(2, 0, 0, 0, 0)                 # what a Ceadeus template leaves
        q.set("category", q.get("category") & ~0x10000000)
        app.editor.reload_tabs()
        app.editor.nb.select(0)
        settle(0.5)
        shot("10_desert_broken")
        gen = app.editor.tabs[0]
        gen._ship_setup(ask=False)
        settle(0.5)
        shot("11_desert_fixed")
        from mhqe import siege
        if not siege.ship_ok(app.editor.quest):
            errors.append("ERROR Dragonship setup did not restore the quest")
    else:
        errors.append("ERROR no Great Desert quest found in the packs")
    for page in ("library", "rom", "pack", "guide"):
        app.show_page(page)
        settle(0.5)
        shot(f"07_page_{page}")
        collect()


try:
    run()
finally:
    for e in errors:
        print(e)
    if LANG != "en":
        miss = sorted(i18n.MISSES)
        print(f"{len(miss)} texts shown without translation:")
        for t in miss:
            print("  ", repr(t[:110]))
    print("DONE" if not errors else "ERRORS")
    app.destroy()
