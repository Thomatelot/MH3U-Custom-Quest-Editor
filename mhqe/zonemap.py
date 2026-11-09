"""The area map of a quest map, with areas lit up in yellow (where a monster or the hunters
start) and small pins on the areas that can be chosen. Click an area or a pin to choose it.

Pure Tk: the map and one transparent overlay per area are pictures built by artbuild.py
(assets/maps/zones), stacked on a canvas once; showing or hiding an area only flips the state
of a canvas item, so nothing is redrawn and nothing flickers.
"""
from __future__ import annotations

import tkinter as tk

from . import theme


class ZoneMap(tk.Canvas):
    def __init__(self, parent, app, map_id: int, target: int = 176, on_pick=None, caption=None, on_click=None):
        self.app, self.map_id, self.on_pick, self.caption = app, map_id, on_pick, caption
        self.on_click = on_click
        self.z = app.icons.zones(map_id)
        size = self.z["size"] if self.z else 160
        # whole zoom, or half size (every other pixel) for small thumbnails of the big maps
        self.zoom = max(1, round(target / size))
        self.sub = 2 if target * 1.6 < size else 1
        side = size * self.zoom // self.sub
        pad = 6
        super().__init__(parent, width=side + 2 * pad, height=side + 2 * pad, highlightthickness=0,
                         borderwidth=0, background=theme.color("map_bg"))
        self.pad, self.side = pad, side
        self._items: dict[str, int] = {}
        self._pins: dict[str, tuple[int, int]] = {}
        self._possible: set[str] = set()
        self._chosen: set[str] = set()
        self._hover: str | None = None
        self.create_rectangle(1, 1, side + 2 * pad - 2, side + 2 * pad - 2, outline=theme.color("map_line"),
                              width=1, tags=("frame",))
        if self.z:
            base = app.icons.zone_layer(map_id, 0, self.zoom, self.sub)
        else:
            base = app.icons.map(map_id, 160)
        self._base = base
        if base is not None:
            self.create_image(pad, pad, image=base, anchor="nw", tags=("base",))
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda _e: self._set_hover(None))
        self.bind("<Button-1>", self._click)
        if on_click is not None:
            self.configure(cursor="hand2")

    # ----------------------------------------------------------------- public
    @property
    def has_areas(self) -> bool:
        return bool(self.z)

    def show(self, chosen=(), possible=()) -> None:
        """Light up the chosen areas (numbers painted on the map) and pin the possible ones."""
        chosen = {str(a) for a in chosen if a is not None}
        possible = {str(a) for a in possible if a is not None}
        if not self.z:
            return
        areas = self.z["areas"]
        for k in set(self._items) | chosen:
            if k not in areas:
                continue
            if k not in self._items:
                img = self.app.icons.zone_layer(self.map_id, areas[k][0], self.zoom, self.sub)
                if img is None:
                    continue
                self._items[k] = self.create_image(self.pad, self.pad, image=img, anchor="nw",
                                                   state="hidden", tags=("zone",))
            self.itemconfigure(self._items[k], state="normal" if k in chosen else "hidden")
        for k in set(self._pins) | possible | chosen:
            if k not in areas:
                continue
            if k not in self._pins:
                x, y = self._xy(k)
                r = 4 + self.zoom if self.sub == 1 else 3
                ring = self.create_oval(x - r, y - r, x + r, y + r, width=2, tags=("pin",))
                dot = self.create_oval(x - 2, y - 2, x + 2, y + 2, width=0, tags=("pin",))
                self._pins[k] = (ring, dot)
            self._style_pin(k, k in chosen, k in possible)
        self.tag_raise("pin")
        self._possible, self._chosen = possible, chosen

    # ---------------------------------------------------------------- helpers
    def _xy(self, k):
        _cell, x, y = self.z["areas"][k]
        f = self.zoom / self.sub
        return self.pad + (x + 0.5) * f, self.pad + (y + 0.5) * f

    def _style_pin(self, k, chosen, possible):
        ring, dot = self._pins[k]
        if not (chosen or possible):
            self.itemconfigure(ring, state="hidden")
            self.itemconfigure(dot, state="hidden")
            return
        hover = k == self._hover
        ink = theme.color("zone_ink")
        fill = theme.color("zone") if (chosen or hover) else "#FFF6DD"
        self.itemconfigure(ring, state="normal", fill=fill, outline=ink, width=3 if hover else 2)
        self.itemconfigure(dot, state="normal", fill=ink if chosen else fill)

    def _area_at(self, ex, ey):
        if not self.z or not self.on_pick:
            return None
        best = None
        for k in self._possible:
            x, y = self._xy(k)
            d = (x - ex) ** 2 + (y - ey) ** 2
            if d <= (10 + 3 * self.zoom) ** 2 and (best is None or d < best[0]):
                best = (d, k)
        if best:
            return best[1]
        f = self.zoom / self.sub
        px, py = int((ex - self.pad) / f), int((ey - self.pad) / f)
        for k in self._possible:
            img = self.app.icons.zone_layer(self.map_id, self.z["areas"][k][0], 1)
            try:
                if img is not None and not img.tk.getboolean(img.tk.call(img, "transparency", "get", px, py)):
                    return k
            except tk.TclError:
                pass
        return None

    def _set_hover(self, k):
        if k == self._hover:
            return
        old, self._hover = self._hover, k
        for kk in (old, k):
            if kk is not None and kk in self._pins:
                self._style_pin(kk, kk in self._chosen, kk in self._possible)
        if self.on_click is None:
            self.configure(cursor="hand2" if k is not None else "")
        if self.caption is not None:
            self.caption(k)

    def _motion(self, e):
        self._set_hover(self._area_at(e.x, e.y))

    def _click(self, e):
        if self.on_click is not None:
            self.on_click()
            return
        k = self._area_at(e.x, e.y)
        if k is not None and self.on_pick:
            self.on_pick(int(k))
