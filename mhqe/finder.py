"""Ctrl+F: find a word in the page or editor tab you are looking at.

The bar searches every visible piece of text of the *current* tab: labels, buttons, field
values, list rows, help bubbles (the "i" dots) and long texts. SelLabel texts are highlighted
in place; other widgets get an outline around them. Enter = next match, Shift+Enter = previous,
Esc = close.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import theme
from .widgets import InfoDot, ScrollFrame, SelLabel, _TtkLabel


class Outline:
    """Four thin frames drawn around a widget (a frame cannot be translucent in Tk)."""

    def __init__(self):
        self.bars: list[tk.Frame] = []

    def show(self, widget, color):
        self.hide()
        try:
            parent = widget.master
            x, y, w, h = widget.winfo_x(), widget.winfo_y(), widget.winfo_width(), widget.winfo_height()
            t = 2
            for bx, by, bw, bh in ((x - t, y - t, w + 2 * t, t), (x - t, y + h, w + 2 * t, t),
                                   (x - t, y, t, h), (x + w, y, t, h)):
                bar = tk.Frame(parent, background=color, borderwidth=0)
                bar.place(x=bx, y=by, width=bw, height=bh)
                bar.lift()
                self.bars.append(bar)
        except tk.TclError:
            self.bars = []

    def hide(self):
        for bar in self.bars:
            try:
                bar.destroy()
            except tk.TclError:
                pass
        self.bars = []


class Finder(ttk.Frame):
    """The find bar. ``scope`` is a function returning the widget whose content is searched."""

    def __init__(self, parent, scope):
        super().__init__(parent, style="Header.TFrame", padding=(10, 4))
        self.scope = scope
        self.var = tk.StringVar()
        self.matches: list[dict] = []
        self.index = -1
        self.outline = Outline()
        ttk.Label(self, text="Find in this tab", style="Header.TLabel", font=theme.FONTS["bold"]).pack(side="left")
        self.entry = ttk.Entry(self, textvariable=self.var, width=34)
        self.entry.pack(side="left", padx=8)
        self.count = ttk.Label(self, text="", style="Header.TLabel", font=theme.FONTS["body"])
        self.count.pack(side="left", padx=(0, 8))
        ttk.Button(self, text="Previous", style="Header.TButton", command=lambda: self.step(-1)).pack(side="left")
        ttk.Button(self, text="Next", style="Header.TButton", command=lambda: self.step(1)).pack(side="left", padx=4)
        ttk.Button(self, text="Close", style="Header.TButton", command=self.close).pack(side="right")
        self.var.trace_add("write", lambda *_a: self.search(jump=True))
        self.entry.bind("<Return>", lambda _e: self.step(1) or "break")
        self.entry.bind("<Shift-Return>", lambda _e: self.step(-1) or "break")
        self.entry.bind("<Escape>", lambda _e: self.close() or "break")

    # ----------------------------------------------------------- open / close
    def open(self):
        if not self.winfo_ismapped():
            self.pack(side="bottom", fill="x", before=self.master.content)
        self.entry.focus_set()
        self.entry.selection_range(0, "end")
        self.search(jump=bool(self.var.get()))

    def close(self):
        self.clear_marks()
        self.pack_forget()
        self.matches, self.index = [], -1

    def refresh(self):
        """Call after the tab changed (page switch, tab switch): searches again in the new tab."""
        if self.winfo_ismapped():
            self.search(jump=False)

    # --------------------------------------------------------------- collecting
    def collect(self, root):
        found = []

        def add(widget, text, kind, **extra):
            text = str(text or "")
            if text.strip():
                found.append({"w": widget, "text": text, "kind": kind, **extra})

        def walk(w):
            if w is self or not w.winfo_exists():
                return
            try:
                if not w.winfo_viewable():
                    return
            except tk.TclError:
                return
            if isinstance(w, SelLabel):
                add(w, w._text, "sel")
            elif isinstance(w, InfoDot):
                add(w, getattr(w, "tip_text", ""), "tip")
            elif isinstance(w, tk.Text):
                add(w, w.get("1.0", "end-1c"), "text")
            elif isinstance(w, ttk.Treeview):
                for iid in w.get_children(""):
                    stack = [iid]
                    while stack:
                        cur = stack.pop()
                        row = " ".join([str(w.item(cur, "text"))] + [str(v) for v in w.item(cur, "values")])
                        add(w, row, "tree", iid=cur)
                        stack.extend(w.get_children(cur))
            elif isinstance(w, (ttk.Entry, ttk.Combobox, ttk.Spinbox)):
                try:
                    add(w, w.get(), "field")
                except tk.TclError:
                    pass
            elif isinstance(w, (_TtkLabel, ttk.Button, ttk.Checkbutton, ttk.Radiobutton, ttk.Labelframe)):
                try:
                    add(w, w.cget("text"), "widget")
                except tk.TclError:
                    pass
            for child in w.winfo_children():
                walk(child)

        walk(root)
        return found

    # ----------------------------------------------------------------- searching
    def search(self, jump=True):
        self.clear_marks()
        needle = self.var.get().strip().lower()
        self.matches, self.index = [], -1
        if not needle:
            self.count.configure(text="")
            return
        root = self.scope()
        if root is None:
            return
        for item in self.collect(root):
            low = item["text"].lower()
            pos, spans = 0, []
            while True:
                i = low.find(needle, pos)
                if i < 0:
                    break
                spans.append((i, i + len(needle)))
                pos = i + max(1, len(needle))
            if spans:
                item["spans"] = spans
                self.matches.append(item)
        total = sum(len(m["spans"]) for m in self.matches)
        self.count.configure(text=f"{total} found" if total else "No match")
        c = theme.current()
        for m in self.matches:
            if m["kind"] == "sel":
                for a, b in m["spans"]:
                    m["w"].tag_add("find", f"1.0+{a}c", f"1.0+{b}c")
                m["w"].tag_configure("find", background=c.get("find", "#ffe08a"), foreground="#1b1b1b")
                m["w"].tag_raise("sel")
        if self.matches and jump:
            self.goto(0)

    def step(self, d):
        if not self.matches:
            self.search(jump=True)
            return
        self.goto((self.index + d) % len(self.matches))

    def goto(self, i):
        self.outline.hide()
        for m in self.matches:
            if m["kind"] == "sel":
                m["w"].tag_remove("findcur", "1.0", "end")
        self.index = i
        m = self.matches[i]
        w = m["w"]
        self.reveal(w, m)
        c = theme.current()
        if m["kind"] == "sel":
            a, b = m["spans"][0]
            w.tag_configure("findcur", background=c.get("find_cur", "#ff9f43"), foreground="#1b1b1b")
            w.tag_add("findcur", f"1.0+{a}c", f"1.0+{b}c")
            w.tag_raise("findcur")
        elif m["kind"] == "text":
            a, b = m["spans"][0]
            w.tag_configure("find", background=c.get("find", "#ffe08a"), foreground="#1b1b1b")
            w.tag_add("find", f"1.0+{a}c", f"1.0+{b}c")
            w.see(f"1.0+{a}c")
        else:
            self.outline.show(w, c.get("find_cur", "#ff9f43"))
        self.count.configure(text=f"{i + 1} / {len(self.matches)}")

    def reveal(self, w, m):
        """Scroll the page so the match is visible."""
        if m["kind"] == "tree":
            try:
                w.see(m["iid"])
                w.selection_set(m["iid"])
            except tk.TclError:
                pass
        parent = w
        while parent is not None and not isinstance(parent, ScrollFrame):
            parent = parent.master
        if parent is None:
            return
        try:
            parent.update_idletasks()
            total = max(1, parent.inner.winfo_height())
            view = max(1, parent.canvas.winfo_height())
            top = w.winfo_rooty() - parent.inner.winfo_rooty()
            if total > view:
                parent.canvas.yview_moveto(max(0.0, min(1.0, (top - view / 3) / total)))
        except tk.TclError:
            pass

    def clear_marks(self):
        self.outline.hide()
        for m in self.matches:
            w = m["w"]
            try:
                if m["kind"] in ("sel", "text"):
                    w.tag_remove("find", "1.0", "end")
                    w.tag_remove("findcur", "1.0", "end")
            except tk.TclError:
                pass
