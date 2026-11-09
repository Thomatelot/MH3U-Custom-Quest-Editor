"""Reusable tkinter widgets: scroll frame, tooltips, info bubbles, stat bars."""
from __future__ import annotations

import math
import tkinter as tk
import weakref
from tkinter import font as tkfont
from tkinter import ttk

from . import theme
from .i18n import _

WHEEL_SEQUENCES = ("<MouseWheel>", "<Shift-MouseWheel>", "<Button-4>", "<Button-5>")


def parse_int(text) -> int:
    t = str(text).strip()
    if not t:
        raise ValueError("empty")
    try:
        return int(t, 10)
    except ValueError:
        return int(t, 0)


def leading_int(label) -> int | None:
    head = str(label).strip().split(" ", 1)[0]
    try:
        return int(head, 10)
    except ValueError:
        return None


def disable_wheel_value_changes(root) -> None:
    """ttk changes a Combobox / Spinbox value when the wheel turns over it, so
    scrolling a page could silently change a field. Remove those bindings."""
    for cls in ("TCombobox", "TSpinbox", "Spinbox"):
        for seq in WHEEL_SEQUENCES:
            try:
                root.unbind_class(cls, seq)
            except tk.TclError:
                pass


def make_modal(win) -> None:
    try:
        win.wait_visibility()
        win.grab_set()
    except tk.TclError:
        pass


def center_on(win, parent) -> None:
    win.update_idletasks()
    try:
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry(f"+{max(0, px + (pw - w) // 2)}+{max(0, py + (ph - h) // 3)}")
    except tk.TclError:
        pass


class ScrollFrame(ttk.Frame):
    """Vertically scrollable frame; put widgets into ``.inner``."""

    def __init__(self, parent, style="TFrame", bg_key="bg"):
        super().__init__(parent, style=style)
        self.bg_key = bg_key
        self.canvas = tk.Canvas(self)
        theme.style_canvas(self.canvas, bg_key)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = ttk.Frame(self.canvas, style=style)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._on_wheel, add="+")
        self.canvas.bind_all("<Button-4>", lambda e: self._scroll(e, -3), add="+")
        self.canvas.bind_all("<Button-5>", lambda e: self._scroll(e, 3), add="+")

    def _pointer_inside(self, event) -> bool:
        # Ask Tcl for the widget *path*: winfo_containing() raises
        # KeyError('popdown') over an open Combobox list in Python 3.14.0.
        try:
            path = str(self.tk.call("winfo", "containing", "-displayof", self._w,
                                    event.x_root, event.y_root))
            if not path or ".popdown" in path:
                return False
            if self.tk.call("winfo", "class", path) in ("Text", "Treeview", "Listbox", "Canvas") \
                    and not path.startswith(str(self.canvas)):
                return False
            if not self.winfo_ismapped():
                return False
        except tk.TclError:
            return False
        me = str(self)
        return path == me or path.startswith(me + ".")

    def _scroll(self, event, units):
        if self._pointer_inside(event) and self.canvas.yview() != (0.0, 1.0):
            self.canvas.yview_scroll(units, "units")

    def _on_wheel(self, event):
        self._scroll(event, int(-1 * (event.delta / 120)) or (-1 if event.delta > 0 else 1))

    def to_top(self):
        self.canvas.yview_moveto(0)


class Tooltip:
    """Hover tooltip. ``text`` may be a string or a callable returning one."""

    enabled = True

    def __init__(self, widget, text, wrap=420, delay=350):
        self.widget, self.text, self.wrap, self.delay = widget, text, wrap, delay
        self.tip = None
        self._after = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def _schedule(self, _e=None):
        self._cancel()
        if Tooltip.enabled:
            self._after = self.widget.after(self.delay, self.show)

    def _cancel(self):
        if self._after:
            try:
                self.widget.after_cancel(self._after)
            except tk.TclError:
                pass
            self._after = None

    def show(self, _e=None):
        text = self.text() if callable(self.text) else self.text
        if not text or self.tip is not None:
            return
        try:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        except tk.TclError:
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        try:
            self.tip.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        c = theme.current()
        lab = tk.Label(self.tip, text=text, justify="left", wraplength=self.wrap,
                       background=c["tip_bg"], foreground=c["tip_ink"], padx=10, pady=7,
                       font=theme.FONTS.get("small"), relief="flat", borderwidth=0)
        lab.pack()
        self.tip.update_idletasks()
        sw = self.widget.winfo_screenwidth()
        if x + self.tip.winfo_reqwidth() > sw - 8:
            x = max(4, sw - self.tip.winfo_reqwidth() - 8)
        self.tip.wm_geometry(f"+{x}+{y}")

    def hide(self, _e=None):
        self._cancel()
        if self.tip is not None:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None


_BG_OF_PREFIX = {"": "bg", "Card.": "card", "Panel.": "panel", "Header": "header"}


class InfoDot(tk.Canvas):
    """A small round (i) drawn in the theme colours; shows ``text`` on hover.
    Drawn (not a font symbol) so it looks the same on every PC."""

    def __init__(self, parent, text, bg_key="bg", size=15):
        super().__init__(parent, width=size, height=size, highlightthickness=0, borderwidth=0,
                         cursor="question_arrow")
        c = theme.current()
        self.configure(background=c[bg_key])
        self.create_oval(1, 1, size - 1, size - 1, fill=c["accent"], outline="")
        self.create_text(size / 2, size / 2 + 0.5, text="i", fill=c["accent_ink"],
                         font=(theme.FONTS["bold"].actual("family"), 8, "bold"))
        self.tip_text = text
        Tooltip(self, text)


def info(parent, text, style_prefix="") -> tk.Canvas:
    """A small (i) bubble that explains a field on hover."""
    return InfoDot(parent, text, _BG_OF_PREFIX.get(style_prefix, "bg"))


class SearchBox(ttk.Frame):
    """Entry with a drawn magnifier (no emoji: they do not render everywhere)."""

    def __init__(self, parent, variable, width=34, bg_key="bg", style="TFrame"):
        super().__init__(parent, style=style)
        c = theme.current()
        cv = tk.Canvas(self, width=18, height=18, highlightthickness=0, borderwidth=0,
                       background=c[bg_key])
        cv.create_oval(2, 2, 12, 12, outline=c["muted"], width=2)
        cv.create_line(11, 11, 16, 16, fill=c["muted"], width=2)
        cv.pack(side="left")
        self.entry = ttk.Entry(self, textvariable=variable, width=width)
        self.entry.pack(side="left", padx=(4, 0), fill="x", expand=True)


class StatusDot(tk.Canvas):
    """A small drawn status mark: 'ok' (check), 'warn' (!) or 'error' (x).
    Drawn rather than typed because symbol glyphs are missing from some fonts."""

    def __init__(self, parent, kind="ok", bg_key="bg", size=18):
        super().__init__(parent, width=size, height=size, highlightthickness=0, borderwidth=0)
        c = theme.current()
        self.configure(background=c[bg_key])
        col = {"ok": c["ok"], "warn": c["warn"], "error": c["danger"]}[kind]
        self.create_oval(1, 1, size - 1, size - 1, fill=col, outline="")
        s = size
        if kind == "ok":
            self.create_line(s * .27, s * .52, s * .44, s * .70, s * .75, s * .32, fill=c["card"], width=2.4,
                             capstyle="round", joinstyle="round")
        elif kind == "warn":
            self.create_line(s / 2, s * .25, s / 2, s * .58, fill=c["card"], width=2.4, capstyle="round")
            self.create_oval(s / 2 - 1.4, s * .70, s / 2 + 1.4, s * .76 + 1.4, fill=c["card"], outline="")
        else:
            self.create_line(s * .32, s * .32, s * .68, s * .68, fill=c["card"], width=2.4, capstyle="round")
            self.create_line(s * .68, s * .32, s * .32, s * .68, fill=c["card"], width=2.4, capstyle="round")


class StatBar(tk.Canvas):
    """Thin horizontal bar (value / maximum)."""

    def __init__(self, parent, width=160, height=8, bg_key="card"):
        super().__init__(parent, width=width, height=height)
        theme.style_canvas(self, bg_key)
        self.w, self.h = width, height
        self.value = 0.0
        self.bind("<Configure>", lambda e: self._draw(e.width))

    def set(self, fraction: float) -> None:
        self.value = max(0.0, min(1.0, fraction))
        self._draw(self.winfo_width() if self.winfo_width() > 1 else self.w)

    def _draw(self, width):
        c = theme.current()
        self.delete("all")
        self.create_rectangle(0, 0, width, self.h, fill=c["bar_bg"], outline="")
        self.create_rectangle(0, 0, int(width * self.value), self.h, fill=c["bar"], outline="")


class Section(ttk.Frame):
    """A titled card used to group fields."""

    def __init__(self, parent, title, tip_text=None):
        super().__init__(parent, style="Box.TFrame", padding=(12, 8, 12, 10))
        head = ttk.Frame(self, style="Card.TFrame")
        head.pack(fill="x", pady=(0, 6))
        ttk.Label(head, text=title, style="Card.H3.TLabel").pack(side="left")
        if tip_text:
            info(head, tip_text, "Card.").pack(side="left", padx=6)
        self.head = head
        self.body = ttk.Frame(self, style="Card.TFrame")
        self.body.pack(fill="both", expand=True)


# ====================================================================================
# Selectable text
# ====================================================================================
_TtkLabel = ttk.Label                      # the real ttk.Label, kept for icon labels
_IGNORED = ("cursor", "takefocus", "underline", "relief", "borderwidth", "class_", "name", "state",
            "compound", "image", "textvariable")


class SelLabel(tk.Text):
    """Drop-in replacement of a ttk.Label for text: it looks the same but the text can be
    selected with the mouse and copied (Ctrl+C or right-click > Copy)."""

    instances: "weakref.WeakSet[SelLabel]" = weakref.WeakSet()

    def __init__(self, parent=None, text="", style="TLabel", wraplength=0, justify="left",
                 anchor="w", font=None, padding=None, width=None, foreground=None, background=None,
                 **kw):
        px = py = 0
        if padding is not None:
            pad = padding if isinstance(padding, (tuple, list)) else (padding,)
            px = int(pad[0])
            py = int(pad[1]) if len(pad) > 1 else px
        super().__init__(parent, height=1, width=1, wrap="none", borderwidth=0, highlightthickness=0,
                         padx=px, pady=py, cursor="arrow", takefocus=0, insertwidth=0, undo=False,
                         spacing1=0, spacing2=0, spacing3=0)
        self._text = _(str(text))
        self._style = style
        self._wrap = int(wraplength or 0)
        self._justify = justify
        self._anchor = anchor
        self._font_opt = font
        self._fg_opt, self._bg_opt = foreground, background
        self._width_opt = width
        self._fitting = False
        self.bind("<Key>", self._key)
        self.bind("<Button-3>", self._menu)
        self.bind("<Configure>", lambda _e: self._fit(), add="+")
        self.bind("<<Paste>>", lambda _e: "break")
        self.bind("<<Cut>>", lambda _e: "break")
        self.bind("<Button-2>", lambda _e: "break")
        SelLabel.instances.add(self)
        self._look()
        self._render()

    # ---------------------------------------------------------------- looks
    def _look(self):
        st = ttk.Style(self)
        bg = self._bg_opt or st.lookup(self._style, "background") or st.lookup("TLabel", "background")
        fg = self._fg_opt or st.lookup(self._style, "foreground") or st.lookup("TLabel", "foreground")
        if self._font_opt is not None:
            font = self._font_opt
        else:
            name = st.lookup(self._style, "font") or "TkDefaultFont"
            try:
                font = tkfont.nametofont(name)
            except tk.TclError:
                font = name
        c = theme.current()
        super().configure(background=bg, foreground=fg, font=font, selectbackground=c["select"],
                          selectforeground=c["select_ink"], inactiveselectbackground=c["select"])
        self._f = font if isinstance(font, tkfont.Font) else tkfont.Font(root=self, font=font)

    def _render(self):
        super().configure(state="normal")
        self.delete("1.0", "end")
        self.insert("1.0", self._text, "body")
        just = {"w": "left", "nw": "left", "sw": "left", "e": "right", "ne": "right", "se": "right",
                "center": "center", "n": "center", "s": "center"}.get(str(self._anchor), "left")
        if self._justify in ("right", "center"):
            just = self._justify
        self.tag_configure("body", justify=just)
        self._size()

    def _size(self):
        f = self._f
        zero = max(1, f.measure("0"))
        lines = self._text.split("\n") or [""]
        if self._wrap > 0:
            chars = max(1, self._wrap // zero)
            limit = chars * zero
            n = 0
            for para in lines:
                cur, rows = 0, 1
                for word in para.split(" "):
                    w = f.measure(word)
                    space = f.measure(" ") if cur else 0
                    if cur and cur + space + w > limit:
                        rows += 1
                        cur = w
                    else:
                        cur += space + w
                n += rows
            super().configure(wrap="word", width=chars, height=max(1, n))
        else:
            longest = max((f.measure(x) for x in lines), default=0)
            width = self._width_opt if isinstance(self._width_opt, int) and self._width_opt > 0 \
                else max(1, math.ceil(longest / zero) + 1)
            super().configure(wrap="none", width=width, height=max(1, len(lines)))

    def _fit(self):
        """Correct the height once Tk knows how the text really wraps."""
        if self._fitting or self._wrap <= 0:
            return
        self._fitting = True
        try:
            n = self.count("1.0", "end-1c", "displaylines")
            n = int(n[0]) if n else 1
            if n > int(self.cget("height")):          # only ever grow: Tk's count is lazy and can read low
                super().configure(height=n)
        except (tk.TclError, TypeError, ValueError):
            pass
        finally:
            self._fitting = False

    # ------------------------------------------------------- label interface
    def configure(self, cnf=None, **kw):
        if isinstance(cnf, str):
            return self.cget(cnf)
        if isinstance(cnf, dict):
            kw = {**cnf, **kw}
        redo = restyle = False
        for key in list(kw):
            if key == "text":
                self._text = _(str(kw.pop(key)))
                redo = True
            elif key == "style":
                self._style = kw.pop(key)
                restyle = redo = True
            elif key == "wraplength":
                self._wrap = int(kw.pop(key) or 0)
                redo = True
            elif key == "justify":
                self._justify = kw.pop(key)
                redo = True
            elif key == "anchor":
                self._anchor = kw.pop(key)
                redo = True
            elif key == "font":
                self._font_opt = kw.pop(key)
                restyle = redo = True
            elif key in ("foreground", "fg"):
                self._fg_opt = kw.pop(key)
                restyle = True
            elif key in ("background", "bg"):
                self._bg_opt = kw.pop(key)
                restyle = True
            elif key == "width":
                self._width_opt = kw.pop(key)
                redo = True
            elif key == "padding":
                pad = kw.pop(key)
                pad = pad if isinstance(pad, (tuple, list)) else (pad,)
                super().configure(padx=int(pad[0]), pady=int(pad[1]) if len(pad) > 1 else int(pad[0]))
            elif key in _IGNORED:
                kw.pop(key)
        if kw:
            super().configure(**kw)
        if restyle:
            self._look()
        if redo:
            self._render()

    config = configure

    def cget(self, key):
        return {"text": self._text, "style": self._style, "wraplength": self._wrap,
                "justify": self._justify, "anchor": self._anchor}.get(key) if key in (
            "text", "style", "wraplength", "justify", "anchor") else super().cget(key)

    __getitem__ = cget

    def __setitem__(self, key, value):
        self.configure(**{key: value})

    def state(self, *_a):          # ttk widget API, nothing to do for a label
        return ()

    def instate(self, *_a):
        return False

    # ----------------------------------------------------------- copy / keys
    def _key(self, event):
        ctrl = bool(event.state & 0x4)
        if ctrl and event.keysym.lower() in ("c", "a", "insert"):
            return None
        if event.keysym in ("Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next", "Shift_L",
                            "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return None
        return "break"

    def _menu(self, event):
        self.focus_set()
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Copy", command=self._copy)
        m.add_command(label="Select all", command=lambda: self.tag_add("sel", "1.0", "end-1c"))
        m.tk_popup(event.x_root, event.y_root)

    def _copy(self):
        try:
            text = self.get("sel.first", "sel.last")
        except tk.TclError:
            text = self._text
        self.clipboard_clear()
        self.clipboard_append(text)


def label_factory(parent=None, **kw):
    """ttk.Label replacement: text labels become selectable, icon labels stay ttk labels."""
    if "text" in kw and not kw.get("image") and "textvariable" not in kw and "compound" not in kw:
        return SelLabel(parent, **kw)
    return _TtkLabel(parent, **kw)


def install_selectable_labels() -> None:
    ttk.Label = label_factory


def copy_tree_selection(tree: ttk.Treeview) -> None:
    """Ctrl+C on a list: copies the selected rows as text (one line per row, tab separated)."""
    lines = []
    for iid in tree.selection():
        cells = [str(tree.item(iid, "text")).strip()] + [str(v) for v in tree.item(iid, "values")]
        lines.append("\t".join(c for c in cells if c))
    if lines:
        tree.clipboard_clear()
        tree.clipboard_append("\n".join(lines))


def enable_tree_copy(root) -> None:
    root.bind_class("Treeview", "<Control-c>", lambda e: copy_tree_selection(e.widget), add="+")


class TribalBand(tk.Canvas):
    """Thin ornamental band in the spirit of MH3U's menus: a gold zig-zag with small diamonds,
    drawn once per width (no redraw while the window is idle)."""

    def __init__(self, parent, height=9, bg_key="header"):
        super().__init__(parent, height=height, highlightthickness=0, borderwidth=0,
                         background=theme.color(bg_key))
        self._drawn = 0
        self.bind("<Configure>", self._draw)

    def _draw(self, e=None):
        w = e.width if e is not None else self.winfo_width()
        if w == self._drawn:
            return
        self._drawn = w
        self.delete("all")
        h = int(self.cget("height"))
        gold, accent = theme.color("gold"), theme.color("accent")
        step = 18
        pts = []
        for i, x in enumerate(range(0, w + step, step // 2)):
            pts += [x, 2 if i % 2 else h - 3]
        if len(pts) >= 4:
            self.create_line(*pts, fill=gold, width=1)
        for x in range(step // 2, w, step * 2):
            m = h // 2
            self.create_polygon(x, m - 3, x + 3, m, x, m + 3, x - 3, m, fill=accent, outline="")
