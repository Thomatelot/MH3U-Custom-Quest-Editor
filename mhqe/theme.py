"""Two themes inspired by Monster Hunter 3 Ultimate's menus, built on ttk 'clam'.

* parchment - "Moga Parchment": the game's quest-paper look (default).
* night     - "Tanzia Night": the dark blue night menus of Port Tanzia.
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

THEMES = {
    "parchment": {
        "name": "Moga Parchment", "desc": "Light: quest paper, leather and ember",
        "bg": "#E9DFC4", "panel": "#F2EAD3", "card": "#FBF6E8", "ink": "#3B2A18",
        "muted": "#76624B", "line": "#C9B48C", "header": "#4B3321", "header_ink": "#F3E6C4",
        "header_hover": "#614330", "accent": "#B5531B", "accent_hover": "#C9662B",
        "accent_ink": "#FFF8EA", "gold": "#B8841F", "select": "#E6CB90", "select_ink": "#2B1D10", "find": "#F4D35E", "find_cur": "#F28C28",
        "danger": "#A3301C", "warn": "#8E6008", "ok": "#4A7526", "entry": "#FFFDF7",
        "stripe": "#F4ECD6", "free": "#9A8869", "bar": "#B5531B", "bar_bg": "#DCCDA8",
        "tip_bg": "#3B2A18", "tip_ink": "#F7EDD3", "group": "#E2D5B4",
        "map_bg": "#2E2216", "map_line": "#6B5236", "zone": "#FFCC28", "zone_ink": "#2B1D10",
    },
    "night": {
        "name": "Tanzia Night", "desc": "Dark: night-blue menus with gold",
        "bg": "#121A26", "panel": "#1A2433", "card": "#202C3F", "ink": "#EDE3C8",
        "muted": "#A39A82", "line": "#34445C", "header": "#0B1018", "header_ink": "#E9D59C",
        "header_hover": "#1C2636", "accent": "#D9A23B", "accent_hover": "#E6B556",
        "accent_ink": "#1A1205", "gold": "#E3B44C", "select": "#33507C", "select_ink": "#FFF6DD", "find": "#B8943A", "find_cur": "#E8782E",
        "danger": "#EC7C64", "warn": "#E6B450", "ok": "#94C66D", "entry": "#0F1520",
        "stripe": "#1D2738", "free": "#6C7688", "bar": "#E3B44C", "bar_bg": "#2C384C",
        "tip_bg": "#E9D59C", "tip_ink": "#121A26", "group": "#16202E",
        "map_bg": "#0B1018", "map_line": "#34445C", "zone": "#FFCC28", "zone_ink": "#1A1205",
    },
}
DEFAULT_THEME = "parchment"

_current = dict(THEMES[DEFAULT_THEME])
FONTS: dict[str, tkfont.Font] = {}


def color(key: str) -> str:
    return _current[key]


def current() -> dict:
    return _current


def _family(root, wanted, fallback):
    have = {f.lower() for f in tkfont.families(root)}
    for name in wanted:
        if name.lower() in have:
            return name
    return fallback


def _make_fonts(root):
    base = tkfont.nametofont("TkDefaultFont").actual()
    body = _family(root, ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", "Ubuntu", "Cantarell",
                          "DejaVu Sans", "Helvetica"), base["family"])
    serif = _family(root, ("Georgia", "Palatino Linotype", "Palatino", "Book Antiqua", "Cambria",
                           "Noto Serif", "DejaVu Serif", "Liberation Serif", "Times New Roman"), body)
    mono = _family(root, ("Consolas", "Menlo", "SF Mono", "DejaVu Sans Mono", "Liberation Mono"), "TkFixedFont")
    up = 3 if sys.platform == "darwin" else 0      # Tk on macOS counts points at 72 dpi: text looks smaller
    spec = {
        "body": (body, 10 + up, "normal"), "small": (body, 9 + up, "normal"), "bold": (body, 10 + up, "bold"),
        "title": (serif, 15 + up, "bold"), "h2": (serif, 12 + up, "bold"), "h3": (serif, 11 + up, "bold"),
        "big": (serif, 18 + up, "bold"), "mono": (mono, 9 + up, "normal"),
        "star": (serif, 12 + up, "bold"),
    }
    for key, (fam, size, weight) in spec.items():
        if key in FONTS:
            FONTS[key].configure(family=fam, size=size, weight=weight)
        else:
            FONTS[key] = tkfont.Font(root=root, family=fam, size=size, weight=weight)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
        tkfont.nametofont(name).configure(family=body, size=10 + up)


def apply(root: tk.Misc, key: str) -> None:
    """Apply a theme to the whole application (can be called again to switch)."""
    _current.clear()
    _current.update(THEMES.get(key, THEMES[DEFAULT_THEME]))
    c = _current
    if not FONTS:
        _make_fonts(root)
    s = ttk.Style(root)
    s.theme_use("clam")
    f = FONTS
    s.configure(".", background=c["bg"], foreground=c["ink"], fieldbackground=c["entry"],
                bordercolor=c["line"], lightcolor=c["panel"], darkcolor=c["line"],
                troughcolor=c["bar_bg"], focuscolor=c["accent"], selectbackground=c["select"],
                selectforeground=c["select_ink"], insertcolor=c["ink"], font=f["body"])
    s.map(".", foreground=[("disabled", c["muted"])])
    for name, bg in (("TFrame", c["bg"]), ("Panel.TFrame", c["panel"]), ("Card.TFrame", c["card"]),
                     ("Header.TFrame", c["header"])):
        s.configure(name, background=bg)
    s.configure("Box.TFrame", background=c["card"], relief="solid", borderwidth=1, bordercolor=c["line"])
    s.configure("TLabel", background=c["bg"], foreground=c["ink"])
    for prefix, bg in (("", c["bg"]), ("Panel.", c["panel"]), ("Card.", c["card"])):
        s.configure(f"{prefix}TLabel", background=bg, foreground=c["ink"])
        s.configure(f"{prefix}Muted.TLabel", background=bg, foreground=c["muted"], font=f["small"])
        s.configure(f"{prefix}H2.TLabel", background=bg, foreground=c["ink"], font=f["h2"])
        s.configure(f"{prefix}H3.TLabel", background=bg, foreground=c["ink"], font=f["h3"])
        s.configure(f"{prefix}Title.TLabel", background=bg, foreground=c["ink"], font=f["title"])
        s.configure(f"{prefix}Gold.TLabel", background=bg, foreground=c["gold"], font=f["star"])
        s.configure(f"{prefix}Accent.TLabel", background=bg, foreground=c["accent"], font=f["bold"])
        s.configure(f"{prefix}Danger.TLabel", background=bg, foreground=c["danger"])
        s.configure(f"{prefix}Warn.TLabel", background=bg, foreground=c["warn"])
        s.configure(f"{prefix}Ok.TLabel", background=bg, foreground=c["ok"])
        s.configure(f"{prefix}Info.TLabel", background=bg, foreground=c["accent"], font=f["bold"])
        s.configure(f"{prefix}TCheckbutton", background=bg, foreground=c["ink"])
        s.configure(f"{prefix}TRadiobutton", background=bg, foreground=c["ink"])
        s.map(f"{prefix}TCheckbutton", background=[("active", bg)], indicatorcolor=[("selected", c["accent"]), ("!selected", c["entry"])])
        s.map(f"{prefix}TRadiobutton", background=[("active", bg)], indicatorcolor=[("selected", c["accent"]), ("!selected", c["entry"])])
    s.configure("Header.TLabel", background=c["header"], foreground=c["header_ink"], font=f["title"])
    s.configure("HeaderMuted.TLabel", background=c["header"], foreground=c["header_ink"], font=f["small"])
    s.configure("Header.TCheckbutton", background=c["header"], foreground=c["header_ink"])
    s.map("Header.TCheckbutton", background=[("active", c["header_hover"])],
          indicatorcolor=[("selected", c["gold"]), ("!selected", c["header"])])
    # buttons
    s.configure("TButton", background=c["panel"], foreground=c["ink"], bordercolor=c["line"],
                padding=(10, 4), relief="flat")
    s.map("TButton", background=[("pressed", c["select"]), ("active", c["card"])],
          bordercolor=[("active", c["accent"])])
    s.configure("Accent.TButton", background=c["accent"], foreground=c["accent_ink"],
                bordercolor=c["accent"], font=f["bold"])
    s.map("Accent.TButton", background=[("disabled", c["panel"]), ("pressed", c["accent"]),
                                        ("active", c["accent_hover"])],
          foreground=[("disabled", c["muted"])], bordercolor=[("disabled", c["line"])])
    s.map("TButton", foreground=[("disabled", c["muted"])])
    s.configure("Header.TButton", background=c["header"], foreground=c["header_ink"],
                bordercolor=c["header"], padding=(9, 6))
    s.map("Header.TButton", background=[("pressed", c["header_hover"]), ("active", c["header_hover"])],
          bordercolor=[("active", c["gold"])])
    s.configure("Nav.TButton", background=c["header"], foreground=c["header_ink"],
                bordercolor=c["header"], padding=(11, 6), font=f["bold"])
    s.map("Nav.TButton", background=[("active", c["header_hover"])])
    s.configure("NavOn.TButton", background=c["bg"], foreground=c["ink"], bordercolor=c["bg"],
                padding=(11, 6), font=f["bold"])
    s.map("NavOn.TButton", background=[("active", c["bg"])])
    s.configure("Link.TButton", background=c["card"], foreground=c["accent"], bordercolor=c["card"],
                padding=(2, 0))
    s.map("Link.TButton", background=[("active", c["card"])], foreground=[("active", c["accent_hover"])])
    s.configure("Tile.TButton", background=c["card"], bordercolor=c["line"], padding=(6, 3), anchor="w")
    s.map("Tile.TButton", background=[("active", c["stripe"])], bordercolor=[("active", c["accent"])],
          foreground=[("disabled", c["muted"])])
    s.configure("Seg.TRadiobutton", background=c["panel"], foreground=c["ink"], padding=(12, 4),
                indicatorsize=0, borderwidth=1, relief="flat")
    s.layout("Seg.TRadiobutton", [("Radiobutton.padding", {"sticky": "nswe", "children": [
        ("Radiobutton.label", {"sticky": "nswe"})]})])
    s.map("Seg.TRadiobutton", background=[("selected", c["accent"]), ("active", c["card"])],
          foreground=[("selected", c["accent_ink"])])
    # entries
    for w in ("TEntry", "TSpinbox", "TCombobox"):
        s.configure(w, fieldbackground=c["entry"], foreground=c["ink"], background=c["panel"],
                    arrowcolor=c["ink"], bordercolor=c["line"], padding=3)
        s.map(w, bordercolor=[("focus", c["accent"])], fieldbackground=[("readonly", c["entry"]), ("disabled", c["panel"])],
              foreground=[("disabled", c["muted"])], selectbackground=[("readonly", c["entry"])],
              selectforeground=[("readonly", c["ink"])])
    s.configure("Bad.TSpinbox", fieldbackground=c["entry"], foreground=c["danger"], bordercolor=c["danger"])
    s.configure("Bad.TEntry", fieldbackground=c["entry"], foreground=c["danger"], bordercolor=c["danger"])
    root.option_add("*TCombobox*Listbox.background", c["entry"])
    root.option_add("*TCombobox*Listbox.foreground", c["ink"])
    root.option_add("*TCombobox*Listbox.selectBackground", c["select"])
    root.option_add("*TCombobox*Listbox.selectForeground", c["select_ink"])
    root.option_add("*TCombobox*Listbox.font", f["body"])
    # tree
    s.configure("Treeview", background=c["card"], fieldbackground=c["card"], foreground=c["ink"],
                bordercolor=c["line"], rowheight=30)
    s.map("Treeview", background=[("selected", c["select"])], foreground=[("selected", c["select_ink"])])
    s.configure("Treeview.Heading", background=c["panel"], foreground=c["ink"], bordercolor=c["line"],
                font=f["bold"], relief="flat", padding=(6, 4))
    s.map("Treeview.Heading", background=[("active", c["stripe"])])
    s.configure("Small.Treeview", rowheight=26)
    s.configure("Item.Treeview", rowheight=26)
    # notebook
    s.configure("TNotebook", background=c["bg"], bordercolor=c["line"], tabmargins=(4, 4, 4, 0))
    s.configure("TNotebook.Tab", background=c["panel"], foreground=c["muted"], padding=(16, 6),
                bordercolor=c["line"], font=f["bold"])
    s.map("TNotebook.Tab", background=[("selected", c["bg"]), ("active", c["card"])],
          foreground=[("selected", c["accent"]), ("active", c["ink"])])
    s.configure("Sub.TNotebook", background=c["bg"], bordercolor=c["line"], tabmargins=(0, 2, 0, 0))
    s.configure("Sub.TNotebook.Tab", background=c["panel"], foreground=c["muted"], padding=(14, 5),
                bordercolor=c["line"], font=f["bold"])
    s.map("Sub.TNotebook.Tab", background=[("selected", c["card"]), ("active", c["card"])],
          foreground=[("selected", c["accent"]), ("active", c["ink"])])
    s.configure("TLabelframe", background=c["bg"], bordercolor=c["line"], relief="solid")
    s.configure("TLabelframe.Label", background=c["bg"], foreground=c["accent"], font=f["h3"])
    s.configure("Card.TLabelframe", background=c["card"], bordercolor=c["line"])
    s.configure("Card.TLabelframe.Label", background=c["card"], foreground=c["accent"], font=f["h3"])
    s.configure("TScrollbar", background=c["panel"], troughcolor=c["bg"], bordercolor=c["line"],
                arrowcolor=c["ink"])
    s.configure("Horizontal.TScale", background=c["accent"], troughcolor=c["bar_bg"])
    s.configure("TSeparator", background=c["line"])
    s.configure("Bar.Horizontal.TProgressbar", background=c["bar"], troughcolor=c["bar_bg"],
                bordercolor=c["line"], lightcolor=c["bar"], darkcolor=c["bar"], thickness=8)
    s.configure("TPanedwindow", background=c["bg"])
    root.configure(background=c["bg"])


def style_text(widget: tk.Text) -> None:
    c = _current
    widget.configure(background=c["entry"], foreground=c["ink"], insertbackground=c["ink"],
                     selectbackground=c["select"], selectforeground=c["select_ink"],
                     highlightthickness=1, highlightbackground=c["line"], highlightcolor=c["accent"],
                     relief="flat", font=FONTS.get("body"))


def style_listbox(widget: tk.Listbox) -> None:
    c = _current
    widget.configure(background=c["entry"], foreground=c["ink"], selectbackground=c["select"],
                     selectforeground=c["select_ink"], highlightthickness=1,
                     highlightbackground=c["line"], relief="flat", font=FONTS.get("body"))


def style_canvas(widget: tk.Canvas, key: str = "bg") -> None:
    widget.configure(background=_current[key], highlightthickness=0, borderwidth=0)
