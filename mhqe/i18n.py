"""English / French interface.

The editor is written in English. ``_()`` gives the French text of an English one when French is
chosen (Settings > Language), from data/lang/fr.json: {"English text": "texte français"}. Keys may
hold ``{}`` for a variable part ("Where {} starts" -> "Où commence {}"), so texts built with
f-strings are translated too.

``install()`` routes every text given to Tk through ``_()``: labels, buttons, check and radio
buttons, tab titles, window titles and message boxes. Most of the editor is therefore translated
without wrapping each string by hand; texts that are not in the dictionary stay in English.
Quest data (names, objectives typed by the user) is never translated.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "lang"
LANGUAGES = {"en": "English", "fr": "Français"}
LANG = "en"
_table: dict[str, str] = {}
_patterns: list[tuple[re.Pattern, str]] = []
_cache: dict[str, str] = {}
MISSES: set[str] = set()          # texts that had no translation (for the developer's check)
_made: set[str] = set()           # texts that are already translations


def system_language() -> str:
    """'fr' when the computer is set to French, else 'en' (first start only; Settings can change it)."""
    import locale
    import os
    for v in (os.environ.get("LC_ALL"), os.environ.get("LC_MESSAGES"), os.environ.get("LANG")):
        if v:
            return "fr" if v.lower().startswith("fr") else "en"
    try:
        loc = locale.getlocale()[0] or ""
    except ValueError:
        loc = ""
    if not loc and sys.platform == "win32":
        try:
            import ctypes
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "fr" if lang_id & 0x3FF == 0x0C else "en"
        except (AttributeError, OSError):
            return "en"
    return "fr" if loc.lower().startswith(("fr", "french")) else "en"


def set_language(code: str) -> None:
    """Choose the language of the texts made from now on (the window is rebuilt after a change)."""
    global LANG, _table, _patterns
    LANG = code if code in LANGUAGES else "en"
    _table, _patterns = {}, []
    _cache.clear()
    _made.clear()
    if LANG == "en":
        return
    try:
        raw = json.loads((DATA / f"{LANG}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    raw.pop("_about", None)
    for src, dst in raw.items():
        if not isinstance(dst, str) or not dst:
            continue
        if "{}" in src:
            parts = [re.escape(p) for p in src.split("{}")]
            _patterns.append((re.compile("^" + "(.+?)".join(parts) + "$", re.S), dst))
        else:
            _table[src] = dst
            _made.add(dst)
    _patterns.sort(key=lambda p: -len(p[0].pattern))
    _long[:] = sorted((k for k in _table if len(k) >= 60), key=len, reverse=True)
    _heads[:] = sorted((k for k in _table if 8 <= len(k) < 60 and k.endswith((". ", ": ", "\n\n", ":\n"))),
                       key=len, reverse=True)


def _(text):
    """The text in the chosen language (unchanged when English or unknown)."""
    if LANG == "en" or not isinstance(text, str) or not text.strip():
        return text
    hit = _cache.get(text)
    if hit is not None:
        return hit
    out = _table.get(text)
    if out is None:
        out = _lines(text)
        if out == text and len(MISSES) < 5000 and re.search(r"[A-Za-z]{3}", text) and text not in _made:
            MISSES.add(text)
    _cache[text] = out
    _made.add(out)
    return out


_long: list[str] = []
_heads: list[str] = []


def _lines(text: str) -> str:
    stripped = text.strip()
    if stripped != text and stripped in _table:          # same text with spaces around it
        return text.replace(stripped, _table[stripped])
    if len(text) > 60:                                    # a long text followed by a short addition
        for key in _long:
            if text.startswith(key):
                return _table[key] + _(text[len(key):])
    for key in _heads:                                    # "Label: " or "Sentence. " followed by more text
        if text.startswith(key) and len(text) > len(key):
            return _table[key] + _(text[len(key):])
    for rx, dst in _patterns:
        m = rx.match(text)
        if m:
            parts = dst.split("{}")
            vals = [_(g) for g in m.groups()]
            if len(parts) - 1 == len(vals):
                return "".join(p + (vals[i] if i < len(vals) else "") for i, p in enumerate(parts))
    if "\n" in text:                                      # paragraphs translated one by one
        bits = text.split("\n")
        if len(bits) > 1:
            done = [_(b) for b in bits]
            if done != bits:
                return "\n".join(done)
    return text


# ------------------------------------------------------------------ Tk hooks
_installed = False


def _fix(cnf):
    if cnf and isinstance(cnf, dict):
        if isinstance(cnf.get("text"), str):
            cnf["text"] = _(cnf["text"])
        vals = cnf.get("values")
        if isinstance(vals, (list, tuple)) and any(isinstance(v, str) for v in vals):
            cnf["values"] = [_(v) if isinstance(v, str) else v for v in vals]
    return cnf


def install() -> None:
    """Translate the texts handed to Tk widgets (once per run)."""
    global _installed
    if _installed:
        return
    _installed = True
    import tkinter as tk                 # here, so that the command-line tools need no Tk
    from tkinter import messagebox, ttk

    base_init = tk.BaseWidget.__init__

    def init(self, master, widgetName, cnf={}, kw={}, extra=()):  # noqa: B006 - Tk's own signature
        if LANG != "en":
            cnf = _fix(dict(cnf)) if cnf else cnf
            kw = _fix(dict(kw)) if kw else kw
        base_init(self, master, widgetName, cnf, kw, extra)
    tk.BaseWidget.__init__ = init

    ttk_init = ttk.Widget.__init__

    def tinit(self, master, widgetname, kw=None):
        if LANG != "en" and kw:
            kw = _fix(dict(kw))
        ttk_init(self, master, widgetname, kw)
    ttk.Widget.__init__ = tinit

    conf = tk.Misc._configure

    def configure(self, cmd, cnf, kw):
        if LANG != "en":
            cnf = _fix(dict(cnf)) if isinstance(cnf, dict) and cnf else cnf
            kw = _fix(dict(kw)) if kw else kw
        return conf(self, cmd, cnf, kw)
    tk.Misc._configure = configure

    for cls, name in ((ttk.Notebook, "add"), (ttk.Notebook, "tab"), (ttk.Notebook, "insert")):
        orig = getattr(cls, name)

        def wrap(*a, _orig=orig, **kw):
            if LANG != "en":
                _fix(kw)
            return _orig(*a, **kw)
        setattr(cls, name, wrap)

    cb_set = ttk.Combobox.set

    def combo_set(self, value):
        return cb_set(self, _(value) if LANG != "en" and isinstance(value, str) else value)
    ttk.Combobox.set = combo_set

    title = tk.Wm.wm_title

    def wm_title(self, string=None):
        return title(self, _(string) if string is not None else None)
    tk.Wm.wm_title = tk.Wm.title = wm_title

    show = messagebox._show

    def _show(title=None, message=None, _icon=None, _type=None, **options):
        if "detail" in options:
            options["detail"] = _(options["detail"])
        return show(_(title), _(message), _icon, _type, **options)
    messagebox._show = _show

    mb_cmd = tk.Menu.add_command

    def add_command(self, cnf={}, **kw):  # noqa: B006
        if LANG != "en" and isinstance(kw.get("label"), str):
            kw["label"] = _(kw["label"])
        return mb_cmd(self, cnf, **kw)
    tk.Menu.add_command = add_command
