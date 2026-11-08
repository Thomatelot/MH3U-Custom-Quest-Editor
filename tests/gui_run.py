"""Scripted run of the real GUI (needs a display, e.g. xvfb-run).

    python tests/gui_run.py <packs_copy_dir> <romfs_dir> <shots_dir> <theme>

Works on a COPY of the quest files. Exercises the main actions (new quest,
edits, save, undo, dev mode, theme switch, backups, library) and saves
screenshots with ImageMagick 'import'. Exits non-zero on any failure.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PACKS, ROMFS, SHOTS, THEME = sys.argv[1:5]
SHOTS = Path(SHOTS)
SHOTS.mkdir(parents=True, exist_ok=True)

from mhqe import project  # noqa: E402

# settings for this run: no first-run dialog, chosen theme, the copied packs
cfg = project.Settings()
cfg.set("setup_done", True)
cfg.set("theme", THEME)
cfg.set("pack_dir", PACKS)
cfg.set("romfs", ROMFS)
cfg.set("dev_mode", False)

from tkinter import messagebox, simpledialog  # noqa: E402

from mhqe import app as A, picker  # noqa: E402
from mhqe.packs import EventPack  # noqa: E402

errors: list[str] = []
picks: list = []          # queued answers for picker._run
_orig_run = picker._run


def fake_run(parent, **kw):
    if picks:
        ans = picks.pop(0)
        return ans(kw["entries"]) if callable(ans) else ans
    return _orig_run(parent, **kw)


picker._run = fake_run
A.picker._run = fake_run
messagebox.askyesno = lambda *a, **k: True
messagebox.askokcancel = lambda *a, **k: True
messagebox.askyesnocancel = lambda *a, **k: False
messagebox.showinfo = lambda *a, **k: errors.append(f"info: {a[1] if len(a) > 1 else a}")
messagebox.showerror = lambda *a, **k: errors.append(f"ERROR dialog: {a[1] if len(a) > 1 else a}")
simpledialog.askstring = lambda *a, **k: "Test Quest Alpha"


def check(cond, msg):
    if not cond:
        errors.append("FAILED: " + msg)
        print("FAILED:", msg, flush=True)
    else:
        print("ok:", msg, flush=True)


from mhqe.widgets import SelLabel, enable_tree_copy, install_selectable_labels  # noqa: E402
from mhqe import editor as E, helptext as H  # noqa: E402
from mhqe import supp as SPmod  # noqa: E402
StartDialogReal = E.StartDialog
install_selectable_labels()
app = A.App()
enable_tree_copy(app)
app.report_callback_exception = lambda exc, val, tb: errors.append(
    "callback: " + "".join(traceback.format_exception(exc, val, tb)))


def settle(t=0.25):
    end = time.time() + t
    while time.time() < end:
        app.update()
        time.sleep(0.02)


def shot(name, window=None):
    settle(0.35)
    wid = str((window or app).winfo_id())
    if window is None:
        wid = app.wm_frame()
    out = SHOTS / f"{THEME}_{name}.png"
    subprocess.run(["import", "-window", wid, str(out)], check=False)
    print("shot", out.name, flush=True)


def run():
    app.geometry("1320x860+0+0")
    settle(0.6)
    ig = app.pages["ingame"]
    check(app.sources["packs"] is not None, "packs found")
    # ---- pictures: the editor ships none; they are built from the player's own game
    if not app.icons.has_art:
        shot("00_no_pictures")
        check(app.icons.monster(41, 27) is not None, "without pictures the editor still returns (empty) images")
        ok = app.build_pictures()
        settle(0.6)
        check(ok and app.icons.has_art, "pictures built from the player's own game")
        ig = app.pages["ingame"]
        app.geometry("1320x860+0+0")
        settle(0.6)
    check(app.icons.monster(41, 27) is not None and app.icons.item(9) is not None, "monster and item pictures available")
    shot("01_ingame_event")
    ig.nb.select(ig.challenge)
    settle()
    shot("02_ingame_challenge")
    ig.nb.select(ig.backups)
    settle()
    shot("03_ingame_backups")
    ig.nb.select(ig.event)
    settle()
    for page in ("library", "rom"):
        app.show_page(page)
        shot(f"04_{page}")
    app.show_page("guide")
    gp = app.pages["guide"]
    n_tabs = len(gp.nb.tabs())
    check(n_tabs >= 7, f"the guide has {n_tabs} tabs")
    for i in range(n_tabs):
        gp.nb.select(i)
        settle(0.3)
        shot(f"04_guide_{i}")
    app.show_page("ingame")
    settle()

    # ---- open an existing event quest and visit the tabs
    ev = ig.event
    first = next(e.key for e in app.sources["packs"].entries() if e.quest is not None and e.group == "quest1")
    q_before = app.sources["packs"].get(first).to_bytes()
    ev.tree.selection_set(first)
    app.edit_selected()
    settle()
    check(app.editor.winfo_ismapped(), "editor opens")
    for i, name in enumerate(("general", "monsters", "supply", "rewards", "text")):
        app.editor.nb.select(i)
        shot(f"05_editor_{i}_{name}")
    # open the collapsible sections for a screenshot
    gen = app.editor.tabs[0]
    app.editor.nb.select(0)
    for w in gen.winfo_children():
        pass
    mon = app.editor.tabs[1]
    for c in mon.cards:
        if c.winfo_ismapped():
            c._toggle(True)
    app.editor.nb.select(1)
    shot("06_editor_monsters_details")

    # ---- edit something, undo it
    q = app.editor.quest
    gen.bound["time_min"][0].set("42")
    settle()
    check(q.get("time_min") == 42, "time limit edited")
    app.editor.undo()
    settle()
    check(q.to_bytes() == q_before, "undo restores the bytes")

    # ---- dev mode on: Advanced tab, raw numbers
    app.dev_mode.set(True)
    app.toggle_dev()
    settle()
    titles = [app.editor.nb.tab(t, "text") for t in app.editor.nb.tabs()]
    check("Advanced" in titles, "dev mode shows the Advanced tab")
    app.editor.nb.select(0)
    shot("07_editor_dev_general")
    app.editor.nb.select(len(titles) - 1)
    shot("08_editor_dev_advanced")
    app.dev_mode.set(False)
    app.toggle_dev()
    settle()
    titles = [app.editor.nb.tab(t, "text") for t in app.editor.nb.tabs()]
    check("Advanced" not in titles, "dev mode off hides the Advanced tab")
    app.show_home()
    settle()

    # ---- new quest in a free slot of pack 3, copying a base-game quest
    src = app.sources["packs"]
    free = [e.key for e in src.entries() if e.quest is None and e.group == "quest3"]
    check(bool(free), "pack 3 has free slots")
    ev.tree.selection_set(free[0])
    settle()
    picks.append(lambda entries: next(e["key"] for e in entries if e.get("cat") == "Game quests"
                                      and "Great Jaggi" in e["sub"]))
    app.new_quest()
    settle()
    nq = src.get(free[0])
    check(nq is not None and nq.get_text("name", 0) == "Test Quest Alpha", "new quest created")
    # edit: objective, monster strength preset, reward
    mon = app.editor.tabs[1]
    card = next(c for c in mon.cards if c.winfo_ismapped())
    card.preset.current(len(card.preset["values"]) - 1)
    card._preset()
    settle()
    app.editor.nb.select(0)
    gen = app.editor.tabs[0]
    gen.bound["reward_money"][0].set("9000")
    settle()
    check(nq.get("penalty") == 3000, "penalty follows reward / 3")
    app.editor.nb.select(1)
    shot("09_new_quest_monsters")
    app.editor.nb.select(0)
    shot("10_new_quest_general")

    # ================= more features =================
    def walk(w):
        yield w
        for c in w.winfo_children():
            yield from walk(c)

    sel = [w for w in walk(app) if isinstance(w, SelLabel)]
    check(len(sel) > 20, f"text labels are selectable ({len(sel)})")
    lab = next(w for w in sel if w.winfo_viewable() and len(w._text) > 8)
    lab.tag_add("sel", "1.0", "end-1c")
    lab._copy()
    check(app.clipboard_get() == lab._text, "selected label text can be copied")
    q2 = src.get(free[0])
    mon = app.editor.tabs[1]
    gen = app.editor.tabs[0]
    sup = app.editor.tabs[2]
    rew = app.editor.tabs[3]
    # developer-only controls are hidden
    app.editor.nb.select(1)
    settle(0.3)
    card = next(c for c in mon.cards if c.winfo_ismapped())
    check(card.stamina is None and "Starttype" not in card.vars, "obscure monster settings hidden outside dev mode")
    check(not hasattr(sup, "bound") or "supp_set_no" not in sup.bound, "second supply delivery hidden outside dev mode")
    # tiers
    slot = card.slot
    q2.set_monster(slot, Nando_hp=96, Nando_at=10, Nando_etc=10)
    mon.do_load(q2)
    check("NIGHTMARE" in card.stats["Nando_hp"].cget("text").upper(), "HP row 96 reads Nightmare")
    q2.set_monster(slot, Nando_hp=42, Nando_at=10, Nando_etc=10)
    mon.do_load(q2)
    check("G Rank" in card.stats["Nando_hp"].cget("text"), "HP row 42 reads G Rank: " + card.stats["Nando_hp"].cget("text"))
    q2.set_monster(slot, Nando_hp=30, Nando_at=30, Nando_etc=30)
    mon.do_load(q2)
    shot("20_tiers")
    # ---- arrival patterns (2.3)
    from mhqe import waves as W, spawns as SPW, strays as ST
    from mhqe import gamedata as GD
    app.editor.nb.select(1)
    settle(0.4)
    check(card.start_btn is None, "'Starts at' is a developer-mode control")
    large = [e for e, n in sorted(GD.MONSTERS.items()) if picker.monster_category(n) == "Large"]
    have = [m["Type"] for m in q2.monsters if m["Type"]]
    while len(set(have)) < 2:
        mon.set_species(len(have), next(e for e in (41, 2, 3, 4) if e not in have))
        have = [m["Type"] for m in q2.monsters if m["Type"]]
    mon.do_load(q2)
    slots = W.used_slots(q2)
    check(mon.order.winfo_manager() == "grid", "arrival section shows with 2 monsters")
    check(len(mon.arrive_box.winfo_children()) == 2, "two arrival choices for two monsters")
    mon.arrive.set(1)
    mon._arrive()
    check(q2.get("start_param") == 1, "'one after the other' writes arrival pattern 1")
    check(q2.objective(1)[2] == q2.monsters[slots[-1]]["Type"] and q2.objective(1)[1] == 4,
          "objective A = the last monster (mode 4)")
    check("→" in mon.phase_lab.cget("text"), "order text shows the sequence")
    check("NOT required" not in mon.win_lab.cget("text"), "a sequence makes every monster required")
    shot("21_arrival")
    first_t = q2.monsters[slots[0]]["Type"]
    last_t = q2.monsters[slots[-1]]["Type"]
    mon.shift(0, 1)
    check(q2.monsters[slots[-1]]["Type"] == first_t and q2.objective(1)[2] == first_t,
          "moving a card later moves the objective with it")
    mon.shift(0, 1)                      # back to the original order
    check(q2.objective(1)[2] == last_t, "objective follows the cards again")
    mon.arrive.set(0)
    mon._arrive()
    check(q2.get("start_param") == 0 and q2.objective(2)[2] != 0, "'both at the start': two objectives")
    # three monsters
    third = next(e for e in large if e not in have)
    mon.set_species(2, third)
    mon.do_load(q2)
    check(len(mon.arrive_box.winfo_children()) == 4, "four arrival choices for three monsters")
    for val, shown in ((5, "1 then 2"), (6, "2 then 1"), (1, "one by one")):
        mon.arrive.set(val)
        mon._arrive()
        groups = W.groups_of(q2)
        check(groups is not None and q2.get("start_param") == val, f"pattern {val} accepted ({shown})")
        check(W.in_sync(q2), f"objectives follow pattern {val}")
    mon.arrive.set(5)
    mon._arrive()
    check(len(W.split(q2, W.groups_of(q2))[-1]) == 2 and "→" in mon.phase_lab.cget("text"), "pattern 5 = one, then two together")
    check(W.covers_all(q2) is False or len(W.derive(q2)[0]) == 2, "win condition text reflects the targets")
    shot("21b_arrival3")
    used3 = W.used_slots(q2)
    names3 = [mon.cards[i].name.cget("text") for i in used3]
    check(all(t.startswith(f"#{k}") for k, t in enumerate(names3, start=1)), f"large monster cards are numbered ({names3})")
    labs = {val: lab.cget("text") for val, (lab, _g) in mon._pat_lab.items()}
    check(len(labs) == 4 and all(t.startswith("To win") for t in labs.values()),
          "every arrival choice says what has to be slain")
    check(labs[0] == W.pattern_win(q2, (3,)) and "all of them" in labs[1],
          "'all at the start' and 'one after another' texts match the objectives rules")
    # size preset
    c0 = mon.cards[used3[0]]
    c0.size_pre.set("King Size (125 %)")
    c0._size_preset()
    check(q2.monsters[used3[0]]["Size"] == 125 and q2.monsters[used3[0]]["Sizeparam"] == 0, "King Size preset sets 125 % and a fixed size")
    check(mon.cards[used3[0]].size_pre.get() == "King Size (125 %)", "the size preset shows the current size")
    c0.size_pre.set("Normal (100 %)")
    c0._size_preset()
    check(q2.monsters[used3[0]]["Size"] == 100, "Normal preset goes back to 100 %")
    # removing back to two monsters keeps a valid pattern
    mon.remove(2)
    check(q2.get("start_param") in (0, 1), "pattern stays valid after removing a monster")
    # start position is a developer-mode setting; the monster keeps the game's choice
    mon.do_load(q2)
    # small monsters: the spawn list
    sl = mon.spawn_list
    if SPW.available() and SPW.readable(q2):
        n0 = len(SPW.species(q2))
        check(n0 >= 1, f"spawn list shows the quest's small monsters ({n0})")
        allowed = {e: n for e, n in SPW.species_on_map(q2.get("map")).items() if e not in SPW.species(q2)}
        before_len = len(q2.to_bytes())
        if allowed:
            picks.append(lambda entries: entries[0]["key"])
            sl.add()
            check(len(SPW.species(q2)) == n0 + 1, "a small monster species was added")
            rm = next(iter(SPW.species(q2)))
            sl.remove(rm)
            check(rm not in SPW.species(q2), "a small monster species was removed")
        check(len(q2.to_bytes()) == before_len, "quest file keeps its size")
        shot("28_spawn_list")
    # environment
    app.editor.nb.select(0)
    gen = app.editor.tabs[0]
    refs = ST.references(q2.get("map"), q2.get("star")) if ST.available() else []
    if refs:
        gen.env.set(1)
        gen._env()
        check(ST.is_unstable(q2) and ST.reference_of(q2) is not None, "Unstable copies a game quest's roaming list")
        gen.sf.canvas.yview_moveto(1.0)
        shot("29_environment")
        gen.sf.canvas.yview_moveto(0.0)
        gen.env.set(0)
        gen._env()
        check(not ST.is_unstable(q2) and q2.get("nora_set_table") == 0, "Stable switches the roaming monsters off")
    # objectives from the monsters
    q2.set_objective(2, 0, 0, 0, 0)
    gen._sync_objectives()
    check(W.in_sync(q2), "'Set the objectives from the monsters' makes the objectives follow the monsters")
    # frozen clock
    app.editor.nb.select(0)
    gen.frozen.set(True)
    gen._frozen()
    check(q2.get("time_min") == 99, "frozen clock sets 99")
    check(any("freeze" in i.text for i in app.editor.issues()), "validate notes the frozen clock")
    gen.frozen.set(False)
    gen._frozen()
    check(q2.get("time_min") == 50, "frozen clock off restores 50")
    # map change replaces the small monsters
    others = [m for m in sorted(GD.MAP_NAMES) if m != q2.get("map") and SPW.species_on_map(m)] if SPW.available() else []
    if others:
        gen._change_map(others[0])
        check(q2.get("map") == others[0], "map changed")
        check(set(SPW.species(q2)) <= set(SPW.species_on_map(others[0])), "small monsters belong to the new map")
    # auto-fill
    E.ask_rank = lambda *a, **k: "HR"
    app.editor.nb.select(1)
    sup._auto()
    check(q2.get("item_set_no") in __import__("mhqe.gamedata", fromlist=["x"]).SUPP_SETS, "supply auto-filled with a game box")
    rew._auto()
    check(len(q2.reward1) > 0, "rewards auto-filled")
    sp = {m["Type"] for m in q2.monsters if m["Type"]}
    from mhqe import autofill as AF
    mats = set().union(*(AF.owners_of(i) for i, _q, _c in q2.reward1))
    check(len(sp & mats) >= min(2, len(sp)), f"rewards hold materials of every monster ({sp & mats} of {sp})")
    check(any(not AF.owners_of(i) for i, _q, _c in q2.reward1), "rewards also hold non-monster items")
    app.editor.nb.select(3)
    settle(0.4)
    shot("27_rewards_auto")
    # custom supply box
    app.editor.nb.select(2)
    sup._make_custom(ask_name=False)
    no = q2.get("item_set_no")
    check(app.boxes.is_custom(no), f"custom supply box created (number {no})")
    check(app.boxes.name(no).startswith("My box"), f"the new box has a default name ({app.boxes.name(no)})")
    app.boxes.set_name(no, "Tracker kit")
    sup._fill_supply()
    check("Tracker kit" in sup.set_lab.cget("text"), "the supply tab shows the box name")
    try:
        app.boxes.set_name(no, "")
        check(False, "an empty box name is refused")
    except SPmod.SuppError:
        check(True, "an empty box name is refused")
    sup._write_box(app.boxes.items(no) + [(1, 7)])
    check((1, 7) in app.boxes.items(no), "item added to the custom box")
    shot("23_supply_custom")
    # box manager, install into / removal from a (fake) Citra folder
    import tempfile
    fake = Path(tempfile.mkdtemp(prefix="fakecitra_")) / "load" / "mods" / "ID" / "romfs"
    fake.mkdir(parents=True)
    orig_fe = A.find_emulator_mod_dirs
    A.find_emulator_mod_dirs = lambda: [fake]
    mgr = E.BoxManager(app)
    settle(0.3)
    check(f"b{no}" in mgr.rows, "the box manager lists the box")
    mgr.tree.selection_set(f"b{no}")
    mgr._detail()
    shot("23b_boxes", window=mgr)
    mgr._install()
    inst = fake / "quest" / "support" / f"supp{no:03d}.supp"
    check(inst.is_file(), "installing copies the supply file into the Citra folder")
    check(SPmod.file_state([inst], app.boxes.items(no)) == "same", "the installed file is the box")
    mgr.fill(f"b{no}")
    check("installed" in mgr.tree.set(f"b{no}", "citra"), "the manager shows the box as installed")
    mgr._remove_file()
    check(not inst.exists() and app.boxes.is_custom(no), "'Remove from Citra' deletes the file and keeps the box")
    mgr._install()
    done, errs = app.delete_box(no)
    check(done == 1 and not errs and not inst.exists() and not app.boxes.is_custom(no),
          "deleting a box also removes its file from Citra")
    mgr.destroy()
    A.find_emulator_mod_dirs = orig_fe
    sup._make_custom(ask_name=False)
    no = q2.get("item_set_no")
    check(app.boxes.is_custom(no), f"a new box can be made again ({no})")
    sup._write_box(app.boxes.items(no) + [(1, 7)])
    # Ctrl+F
    app.editor.nb.select(0)
    app.find_here()
    app.finder.var.set("objective")
    settle(0.5)
    check(len(app.finder.matches) > 0, f"Ctrl+F finds text in the General tab ({len(app.finder.matches)})")
    app.finder.step(1)
    shot("24_find")
    app.editor.nb.select(2)
    settle(0.5)
    app.finder.var.set("box")
    settle(0.4)
    check(len(app.finder.matches) > 0, "Ctrl+F searches the current tab (Supply Box)")
    app.finder.close()
    # save writes the supply file
    ok = app.save()
    from pathlib import Path as _P
    f = A.SUPPLY_OUTPUT / "quest" / "support" / f"supp{no:03d}.supp"
    check(ok and f.is_file(), "save writes the custom supply file")
    from mhqe import supp as SP
    check((1, 7) in SP.read_supp(f.read_bytes()), "supply file contains the added item")

    def truncated():
        bad = []
        for w in walk(app):
            if isinstance(w, SelLabel) and w.winfo_viewable() and w._text.strip():
                try:
                    if w.dlineinfo("end-1c") is None:
                        bad.append(w._text[:40])
                except Exception:
                    pass
        return bad
    for i in range(len(app.editor.tabs)):
        app.editor.nb.select(i)
        settle(0.5)
        check(not truncated(), f"no clipped text on tab {i}: {truncated()}")
    check(not truncated(), "no clipped text")
    # dev mode shows the hidden controls
    app.dev_mode.set(True)
    app.toggle_dev()
    settle()
    mon = app.editor.tabs[1]
    app.editor.nb.select(1)
    settle(0.4)
    card = next(c for c in mon.cards if c.winfo_ismapped())
    check(card.stamina is not None and "Starttype" in card.vars, "dev mode shows the obscure monster settings")
    check(card.start_btn is not None, "dev mode shows the start-position button")
    import mhqe.editor as _E2
    def _fake_dialog(app_, map_id, cur, name, em=None):
        import tkinter as _tk
        d = _tk.Toplevel(app_)
        d.result = 3
        d.after(50, d.destroy)
        return d
    _E2.StartDialog = _fake_dialog
    qd = app.editor.quest
    check(qd is app.sources["packs"].get(free[0]), "the editor edits the very quest object that is saved")
    card._start()
    check(qd.monsters[card.slot]["Starttype"] == 3, f"start position written to the monster (developer mode) {qd.monsters[card.slot]['Starttype']}")
    _E2.StartDialog = StartDialogReal
    dlg = StartDialogReal(app, qd.get("map"), 3, "Test")
    settle(1.0)
    shot("26_start_dialog", dlg)
    dlg.destroy()
    qd.set_monster(card.slot, Starttype=0)
    mon.do_load(qd)
    app.editor.nb.select(1)
    shot("25_dev_monsters")
    app.dev_mode.set(False)
    app.toggle_dev()
    settle()
    # release the test box
    app.sources["packs"].get(free[0]).set("item_set_no", 1)
    app.delete_box(no)

    ok = app.save()
    settle()
    check(ok, "save succeeded")
    pack = EventPack(os.path.join(PACKS, "quest3"))
    names = [s.quest.get_text("name", 0) for s in pack.used_slots()]
    check("Test Quest Alpha" in names, "new quest written to quest3")
    check(any(app.backups.list_full()), "full backup made on save")

    # ---- library: copy, then put back into the game via 'To game'
    app.show_home()
    settle()
    ev.tree.selection_set(free[0])
    app.to_library()
    lib = app.sources["library"]
    check(any(q.get_text("name", 0) == "Test Quest Alpha" for q in lib.quests.values()), "copied to library")
    app.show_page("library")
    settle()
    shot("11_library_with_quest")

    # ---- clear the slot (backup of the replaced quest is kept on save)
    app.show_page("ingame")
    settle()
    ev.tree.selection_set(free[0])
    app.clear_slot()
    app.save()
    settle()
    check(src.get(free[0]) is None, "slot cleared")
    check(any(b.get("name") == "Test Quest Alpha" for b in app.backups.list_quests()),
          "cleared quest kept in backups")
    ig.nb.select(ig.backups)
    settle()
    shot("12_backups_after")
    ig.nb.select(ig.event)

    # ---- check the first quest we opened was never changed
    check(src.get(first).to_bytes() == q_before, "untouched quest unchanged after saves")

    # ---- dialogs: settings (theme previews) and a real picker
    def grab_toplevel(name):
        tops = [w for w in app.winfo_children() if w.winfo_class() == "Toplevel" and w.winfo_ismapped()]
        if tops:
            shot(name, tops[-1])
            tops[-1].destroy()
    app.after(900, lambda: grab_toplevel("13_settings"))
    app.open_settings()
    settle(1.2)
    app.after(900, lambda: grab_toplevel("14_picker_monsters"))
    picker.pick_monster(app)              # real dialog (no queued answer)
    settle(1.2)

    # ---- 1.1: monster pack page (ROM hack) and game versions
    import tempfile
    from mhqe import gamedata as G, monsterpack as MP
    app.show_page("pack")
    shot("15_pack_before")
    app.build_monster_pack()
    end = time.time() + 120
    while time.time() < end and MP.read_manifest(app.monster_pack_dir()) is None:
        settle(0.5)
    settle(1.0)
    man = MP.read_manifest(app.monster_pack_dir())
    check(man is not None and len(man["added"]) > 300, "monster pack built from the game")
    fake_citra = Path(tempfile.mkdtemp()) / "load" / "mods" / G.TITLE_ID
    A.find_emulator_title_dirs = lambda: [fake_citra]
    app.install_monster_pack()
    settle()
    inst, where = app.installed_monster_pack()
    check(inst is not None and inst["fingerprint"] == man["fingerprint"], "pack installed (fake Citra folder)")
    check(app.monster_pack() == (inst, True), "quest checks use the installed pack")
    shot("16_pack_installed")
    dlg = StartDialogReal(app, 2, 0, "Zinogre", em=41)
    settle(0.5)
    check(dlg.areas == [6, 7, 8], f"start areas of Zinogre on Sandy Plains from the pack: {dlg.areas}")
    shot("17_start_dialog_pack", dlg)
    dlg.destroy()
    app.remove_monster_pack()
    settle()
    check(app.installed_monster_pack() == (None, None), "pack removed")
    check(not (fake_citra / "exefs" / "code.ips").exists(), "code.ips removed")
    app.switch_region("us")
    settle(0.6)
    check(G.TITLE_ID == "00040000000AE400" and G.EXTDATA_ID == "00000AE4", "switched to the US version")
    check(app.sources["packs"] is None, "the EU save is not used for the US version")
    app.show_page("pack")
    shot("18_pack_us")
    app.switch_region("eu")
    settle(0.6)
    check(G.TITLE_ID == "00040000000B1D00" and app.sources["packs"] is not None, "back to the EU version and its save")


try:
    run()
except Exception:
    errors.append(traceback.format_exc())
finally:
    try:
        app.destroy()
    except Exception:
        pass

print("\n".join(errors) if errors else "ALL GOOD")
sys.exit(1 if any(e.startswith(("FAILED", "ERROR", "callback", "Traceback")) for e in errors) else 0)
