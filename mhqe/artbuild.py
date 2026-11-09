"""Builds the editor's pictures (monster, item and map icons) from YOUR copy of the game.

The pictures already ship in the editor's ``assets/`` folder. This module can rebuild them from your own
extracted game (e.g. if they are missing), writing into ``assets/`` next to the program.
It is used by Settings > "Rebuild the pictures from my game" and by ``tools/build_assets.py``.

Needs Pillow (``pip install pillow``) and the extracted game:
  romfs      the game's ``romfs`` folder (monster icons and area maps)
  code.bin   optional, ``exefs/code.bin`` of the same game (item icons: shape and colour of each item)

Where each picture comes from:
  * Item icons: the game's own icon sheet (GUI/Texture/common/td_icon_ID_eng, 130 white shapes of 22 px)
    tinted with the colour of each item's record in code.bin.
  * Monster icons: the game's monster icon sheet (td_icon_m_ID_eng in arc/ID/ID_com_eng.arc, 9 x 9 cells
    of 54 px). Which cell belongs to which monster was identified by comparing with the MH3U wiki icons.
  * Map images: the in-game area maps (arc/ID/map/ID_map_NN.arc).
"""
from __future__ import annotations

import glob
import json
import os
import re
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ArtError(RuntimeError):
    pass


def pillow_available() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def default_code_bin(romfs) -> Path | None:
    """exefs/code.bin next to the romfs folder (the usual layout of a dumped game), if it exists."""
    p = Path(romfs).parent / "exefs" / "code.bin"
    return p if p.is_file() else None


ITEM_RECORD_SIZE = 20
ITEM_CELL = 22
ATLAS_COLUMNS = 10
ATLAS_CELLS = 130
MON = (54, 27)

# Colour ids of the item records -> RGB. Measured on the wiki's MH3 icons
# against the game's white shapes (median fill ratio), then lightly brightened.
PALETTE = {
    0: (232, 232, 232), 1: (214, 77, 77), 2: (98, 176, 119), 3: (99, 121, 172),
    4: (197, 164, 71), 5: (146, 116, 154), 6: (113, 159, 179), 7: (206, 131, 73),
    8: (191, 119, 132), 9: (72, 130, 89), 10: (134, 134, 134), 11: (211, 177, 75),
    12: (58, 141, 121), 13: (72, 130, 89),
}
PALETTE_NAMES = {0: "White", 1: "Red", 2: "Green", 3: "Blue", 4: "Yellow",
                 5: "Purple", 6: "Light blue", 7: "Orange", 8: "Pink",
                 9: "Dark green", 10: "Grey", 11: "Gold", 12: "Teal", 13: "Moss"}

# quest map id -> map texture (ID_map archive, texture name)
MAP_TEXTURES = {
    1: "td_map_m01d_ID", 2: "td_map_m02d_ID", 3: "td_map_m03d_ID", 4: "td_map_m04d_ID",
    5: "td_map_m05d_ID", 6: "td_map_m06d_1_ID", 7: "td_map_m07d_ID", 8: "td_map_m08d_riku_ID",
    9: "td_map_m09d_riku_ID", 10: "td_map_m09d_mizu_ID", 11: "td_map_m10d_ID",
    12: "td_map_m11d_mizu_ID", 13: "td_map_m12d_ID", 14: "td_map_m13d_ID", 15: "td_map_m14d_ID",
}

MON_CELL = 54
# em id -> cell of td_icon_m_ID_eng (row-major, 9 per row)
EM_CELL = {
    1: 22, 2: 23, 3: 21, 4: 25, 5: 26, 6: 24, 7: 32, 8: 19, 9: 20, 10: 10, 11: 11, 12: 17,
    13: 12, 14: 18, 15: 29, 16: 27, 17: 13, 18: 28, 19: 30, 20: 31, 21: 14, 22: 15, 23: 2,
    24: 35, 25: 33, 26: 9, 27: 0, 28: 3, 29: 16, 30: 6, 31: 7, 32: 8, 33: 5, 34: 1, 35: 78,
    36: 4, 37: 4, 38: 4, 39: 4, 40: 77, 41: 36, 42: 37, 43: 38, 44: 39, 45: 40, 46: 41,
    47: 42, 48: 43, 49: 44, 50: 79, 51: 45, 52: 46, 53: 47, 54: 48, 55: 49, 56: 50, 57: 51,
    58: 52, 59: 53, 60: 54, 61: 55, 62: 56, 63: 57, 64: 58, 65: 59, 66: 60, 67: 61, 68: 62,
    69: 63, 70: 64, 71: 65, 72: 66, 73: 67, 74: 68, 75: 35, 76: 69, 77: 71, 78: 44, 79: 77,
    80: 77, 81: 77, 82: 77, 83: 77, 84: 77, 85: 70,
}
# other icons of the same sheet used by the editor
SPECIAL_CELLS = {"delivery": 80, "unknown": 35, "danger": 34}
# monsters the game shows with a shared or placeholder icon
SHARED_ICON = {24: "the game shows '?' for Alatreon", 75: "the game shows '?' for Dire Miralis",
               36: "one Bnahabra icon for every colour", 37: "one Bnahabra icon for every colour",
               38: "one Bnahabra icon for every colour", 39: "one Bnahabra icon for every colour",
               78: "same icon as Slagtoth", 40: "boulder icon", 79: "boulder icon", 80: "boulder icon",
               81: "boulder icon", 82: "boulder icon", 83: "boulder icon", 84: "boulder icon"}


# ------------------------------------------------------------- map areas
ZONE_FILL = (255, 204, 40, 115)        # chosen area: warm yellow wash...
ZONE_EDGE = (255, 232, 92, 255)        # ...with a bright rim


def _is_area_pixel(p) -> bool:
    """Coloured area of the map picture (not the grey paths, the white numbers or the background)."""
    r, g, b, a = p
    if a < 160 or min(r, g, b) > 225:
        return False
    mx, mn = max(r, g, b), min(r, g, b)
    v, s = mx / 255, (mx - mn) / mx if mx else 0
    return (s >= 0.16 and v >= 0.28) or (v >= 0.75 and s >= 0.08)


def zone_masks(img, seeds: dict) -> dict:
    """Area number -> set of pixels of that area on the map picture. Each seed (an area's centre)
    takes the coloured blob under it (or the nearest one); a blob holding several seeds is split
    between them; a seed with no blob near it gets a small disc."""
    w, h = img.size
    px = img.load()
    mask = [[_is_area_pixel(px[x, y]) for x in range(w)] for y in range(h)]
    label = [[0] * w for _ in range(h)]
    blobs = [None]
    for y in range(h):
        for x in range(w):
            if mask[y][x] and not label[y][x]:
                n = len(blobs)
                stack, pts = [(x, y)], []
                label[y][x] = n
                while stack:
                    cx, cy = stack.pop()
                    pts.append((cx, cy))
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] and not label[ny][nx]:
                            label[ny][nx] = n
                            stack.append((nx, ny))
                blobs.append(pts)
    owner: dict[int, list] = {}
    for k, (sx, sy) in seeds.items():
        ix, iy = int(round(sx)), int(round(sy))
        best = None
        for r in range(0, 7):
            for yy in range(iy - r, iy + r + 1):
                for xx in range(ix - r, ix + r + 1):
                    if 0 <= xx < w and 0 <= yy < h and label[yy][xx] and len(blobs[label[yy][xx]]) >= 20:
                        d = (xx - sx) ** 2 + (yy - sy) ** 2
                        if best is None or d < best[0]:
                            best = (d, label[yy][xx])
            if best:
                break
        if best:
            owner.setdefault(best[1], []).append(k)
    out = {}
    for n, keys in owner.items():
        if len(keys) == 1:
            out[keys[0]] = set(blobs[n])
            continue
        for k in keys:
            out[k] = set()
        for x, y in blobs[n]:
            k = min(keys, key=lambda kk: (x - seeds[kk][0]) ** 2 + (y - seeds[kk][1]) ** 2)
            out[k].add((x, y))
    for k, (sx, sy) in seeds.items():
        if k not in out:
            out[k] = {(x, y) for x in range(int(sx) - 6, int(sx) + 7) for y in range(int(sy) - 6, int(sy) + 7)
                      if (x - sx) ** 2 + (y - sy) ** 2 <= 36 and 0 <= x < w and 0 <= y < h}
    return out


def zone_sheet(img, bbox, seeds: dict, path) -> dict:
    """One strip per map: the map (cropped to bbox, on a square) then one yellow overlay per area,
    all the same size, so the editor can stack them on a canvas without Pillow."""
    from PIL import Image
    masks = zone_masks(img, seeds)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    side = max(bw, bh)
    ox, oy = (side - bw) // 2 - bbox[0], (side - bh) // 2 - bbox[1]
    keys = sorted(masks, key=int)
    sheet = Image.new("RGBA", (side * (len(keys) + 1), side))
    sheet.paste(img.crop(bbox), (ox + bbox[0], oy + bbox[1]))
    areas = {}
    for cell, k in enumerate(keys, start=1):
        pts = {(x + ox, y + oy) for x, y in masks[k] if 0 <= x + ox < side and 0 <= y + oy < side}
        if not pts:
            continue
        sp = sheet.load()
        base = cell * side
        for x, y in pts:
            sp[base + x, y] = ZONE_FILL
        for x, y in pts:
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1),
                           (x + 1, y + 1), (x - 1, y - 1), (x + 1, y - 1), (x - 1, y + 1)):
                if (nx, ny) not in pts and 0 <= nx < side and 0 <= ny < side:
                    sp[base + nx, ny] = ZONE_EDGE
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        areas[k] = [cell, round(cx), round(cy)]
    sheet.save(path)
    return {"size": side, "file": f"maps/zones/{path.name}", "areas": areas}


def arc_entries(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    _v, count = struct.unpack_from("<HH", raw, 4)
    for i in range(count):
        o = 12 + i * 80
        name = raw[o:o + 64].split(b"\0", 1)[0].decode("ascii", "replace")
        type_hash, csize, _dsize, off = struct.unpack_from("<IIII", raw, o + 64)
        yield name, type_hash, raw, off, csize


def find_item_table(code: bytes) -> int:
    """Locate the item records: Potion..Mega Demondrug sell prices (items 9-18)."""
    sell = [7, 16, 25, 92, 6, 92, 29, 205, 67, 283]
    pat = struct.pack("<I", sell[0])
    i = code.find(pat)
    while i != -1:
        if all(struct.unpack_from("<I", code, i + ITEM_RECORD_SIZE * k)[0] == sell[k] for k in range(10)):
            return i - 12 - 9 * ITEM_RECORD_SIZE
        i = code.find(pat, i + 1)
    raise ArtError("the item table was not found in code.bin (is it MH3U, EU or US version?)")


def tint(cell, rgb):
    from PIL import Image
    out = Image.new("RGBA", cell.size)
    px, po = cell.load(), out.load()
    for y in range(cell.size[1]):
        for x in range(cell.size[0]):
            r, g, b, a = px[x, y]
            po[x, y] = (r * rgb[0] // 255, g * rgb[1] // 255, b * rgb[2] // 255, a)
    return out


def build(romfs, out=ROOT, code=None, wiki=None, log=print) -> dict:
    """Write assets/ and update data/icons.json under ``out``. Returns a short summary."""
    try:
        from PIL import Image
    except ImportError:
        raise ArtError("Pillow is needed to read the game's pictures: run  pip install pillow") from None
    from . import tex3ds
    romfs, out = Path(romfs), Path(out)
    com = romfs / "arc" / "ID" / "ID_com_eng.arc"
    if not com.is_file():
        raise ArtError(f"{com} was not found: choose the game's romfs folder.")
    assets = out / "assets"
    (assets / "maps").mkdir(parents=True, exist_ok=True)
    index_path = out / "data" / "icons.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        index = {}

    def sheet_of(suffix):
        for name, _th, raw, off, cs in arc_entries(str(com)):
            if name.endswith(suffix):
                return tex3ds.decode(zlib.decompress(raw[off:off + cs]))[0]
        return None

    # ---------------------------------------------------------------- items
    n_items = 0
    if code:
        atlas = sheet_of("td_icon_ID_eng")
        if atlas is None:
            raise ArtError("the item icon sheet was not found in the game")
        codeb = Path(code).read_bytes()
        base = find_item_table(codeb)
        items_names = json.loads((out / "data" / "items_en.json").read_text(encoding="utf-8"))["items"]

        def cell_of(sh):
            x, y = (sh % ATLAS_COLUMNS) * ITEM_CELL, (sh // ATLAS_COLUMNS) * ITEM_CELL
            return atlas.crop((x, y, x + ITEM_CELL, y + ITEM_CELL))
        items, combos = {}, []
        for iid in range(len(items_names)):
            o = base + iid * ITEM_RECORD_SIZE
            shape, colour = codeb[o], codeb[o + 1]
            if shape >= ATLAS_CELLS or colour not in PALETTE:
                continue
            key = (shape, colour)
            if key not in combos:
                combos.append(key)
            items[str(iid)] = combos.index(key)
        cols = 20
        sheet = Image.new("RGBA", (cols * ITEM_CELL, ((len(combos) + cols - 1) // cols) * ITEM_CELL))
        for k, (shape, colour) in enumerate(combos):
            sheet.paste(tint(cell_of(shape), PALETTE[colour]), ((k % cols) * ITEM_CELL, (k // cols) * ITEM_CELL))
        sheet.save(assets / "items.png")
        index.update({"item_cell": ITEM_CELL, "item_columns": cols, "items": items,
                      "item_combos": [[s, c] for s, c in combos],
                      "palette_names": {str(k): v for k, v in PALETTE_NAMES.items()}})
        n_items = len(items)
        log(f"item icons: {n_items} items")
    else:
        log("item icons skipped (no code.bin)")

    # -------------------------------------------------------------- monsters
    msheet_src = sheet_of("td_icon_m_ID_eng")
    if msheet_src is None:
        raise ArtError("the monster icon sheet was not found in the game")

    def cell_img(c):
        x, y = (c % 9) * MON_CELL, (c // 9) * MON_CELL
        return msheet_src.crop((x, y, x + MON_CELL, y + MON_CELL))
    cells = sorted(set(EM_CELL.values()) | set(SPECIAL_CELLS.values()))
    slot_of_cell = {c: k for k, c in enumerate(cells)}
    if wiki:                       # optional double check against saved wiki pages (developer use)
        mons = json.loads((out / "data" / "monsters.json").read_text(encoding="utf-8"))["monsters"]
        wk = {}
        for f in glob.glob(os.path.join(wiki, "*_files", "MH3U-*Icon*")):
            key = re.sub(r"^MH3U-|_Icon.*$", "", os.path.basename(f)).replace("_", " ")
            wk.setdefault(key, f)

        def vec(img):
            img = img.convert("RGBA").resize((27, 27), Image.LANCZOS)
            bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
            bg.alpha_composite(img)
            return list(bg.convert("RGB").getdata())
        cv = {c: vec(cell_img(c)) for c in cells}
        bad = 0
        for em, info in sorted(mons.items(), key=lambda kv: int(kv[0])):
            if info["name"] not in wk:
                continue
            wv = vec(Image.open(wk[info["name"]]))
            best = min(cv, key=lambda c: sum((x - y) ** 2 for p, q in zip(wv, cv[c]) for x, y in zip(p, q)))
            if best != EM_CELL[int(em)]:
                bad += 1
                log(f"  check: wiki icon of {info['name']} looks like cell {best}, table says {EM_CELL[int(em)]}")
        log(f"monster icons checked against {len(wk)} wiki icons: {bad} difference(s)")
    for size in MON:
        mcols = 12
        msheet = Image.new("RGBA", (mcols * size, ((len(cells) + mcols - 1) // mcols) * size))
        for k, c in enumerate(cells):
            msheet.paste(cell_img(c).resize((size, size), Image.LANCZOS), ((k % mcols) * size, (k // mcols) * size))
        msheet.save(assets / f"monsters_{size}.png")
    log(f"monster icons: {len(EM_CELL)} monsters")

    # ------------------------------------------------------------------ maps
    textures = {}
    for f in sorted(glob.glob(str(romfs / "arc" / "ID" / "map" / "ID_map_*.arc"))):
        for name, th, raw, off, cs in arc_entries(f):
            leaf = name.split("\\")[-1]
            if th == 0x241f5deb and leaf.startswith("td_map_") and leaf not in textures:
                textures[leaf] = tex3ds.decode(zlib.decompress(raw[off:off + cs]))[0]
    maps = {}
    zone_index = {}
    try:
        seeds_file = out / "data" / "map_zones.json"
        if not seeds_file.is_file():
            seeds_file = ROOT / "data" / "map_zones.json"
        zone_seeds = json.loads(seeds_file.read_text(encoding="utf-8"))["maps"]
    except (OSError, ValueError, KeyError):
        zone_seeds = {}
    (assets / "maps" / "zones").mkdir(parents=True, exist_ok=True)
    for qmap, leaf in MAP_TEXTURES.items():
        if leaf not in textures:
            continue
        img = textures[leaf]
        bbox = img.split()[3].point(lambda v: 255 if v > 24 else 0).getbbox()
        if bbox:
            pad = 6
            bbox = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                    min(img.size[0], bbox[2] + pad), min(img.size[1], bbox[3] + pad))
        else:
            bbox = (0, 0) + img.size
        if str(qmap) in zone_seeds:
            zone_index[str(qmap)] = zone_sheet(img.convert("RGBA"), bbox, zone_seeds[str(qmap)],
                                               assets / "maps" / "zones" / f"map{qmap:02d}.png")
        img = img.crop(bbox)
        for size in (160, 64):
            canvas = Image.new("RGBA", (size, size))
            t = img.copy()
            t.thumbnail((size, size), Image.LANCZOS)
            canvas.paste(t, ((size - t.size[0]) // 2, (size - t.size[1]) // 2), t)
            canvas.save(assets / "maps" / f"map{qmap:02d}_{size}.png")
        maps[str(qmap)] = f"maps/map{qmap:02d}"
    log(f"map pictures: {len(maps)}, with areas: {len(zone_index)}")

    index.update({
        "_about": "Index of the pictures built by mhqe/artbuild.py from the game's own files.",
        "monster_sizes": list(MON), "monster_columns": 12,
        "monsters": {str(em): slot_of_cell[c] for em, c in EM_CELL.items()},
        "monsters_shared": {str(em): why for em, why in SHARED_ICON.items()},
        "special": {k: slot_of_cell[c] for k, c in SPECIAL_CELLS.items()},
        "maps": maps,
        "zones": zone_index,
    })
    index_path.write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
    return {"items": n_items, "monsters": len(EM_CELL), "maps": len(maps)}
