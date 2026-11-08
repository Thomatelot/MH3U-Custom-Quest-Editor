"""Draws the editor's own icon (an original drawing: a quest scroll with a red wax seal).

    python tools/make_icon.py      ->  assets/app_icon.png (48 px), app_icon_256.png, app_icon.ico

Needs Pillow. The result is committed, so you only run this to change the icon.
"""
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def draw(size=512):
    s = size
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = s / 100
    ink, paper, shade, wood = (74, 48, 28), (244, 232, 200), (222, 202, 160), (140, 90, 50)
    # scroll body
    d.rounded_rectangle((18 * u, 14 * u, 82 * u, 86 * u), radius=3 * u, fill=paper, outline=ink, width=int(2 * u))
    # top and bottom rolls
    for y in (14, 86):
        d.rounded_rectangle((12 * u, (y - 6) * u, 88 * u, (y + 6) * u), radius=6 * u, fill=wood, outline=ink, width=int(2 * u))
        d.ellipse((8 * u, (y - 6) * u, 20 * u, (y + 6) * u), fill=shade, outline=ink, width=int(2 * u))
        d.ellipse((80 * u, (y - 6) * u, 92 * u, (y + 6) * u), fill=shade, outline=ink, width=int(2 * u))
    # text lines
    for i, w in enumerate((46, 38, 46, 30)):
        y = (28 + i * 8) * u
        d.rounded_rectangle((27 * u, y, (27 + w) * u, y + 3 * u), radius=1.5 * u, fill=ink)
    # check mark
    d.line((30 * u, 62 * u, 38 * u, 70 * u, 52 * u, 54 * u), fill=(176, 64, 24), width=int(4 * u), joint="curve")
    # wax seal
    cx, cy, r = 68 * u, 68 * u, 13 * u
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(176, 40, 32), outline=(110, 24, 20), width=int(2 * u))
    d.ellipse((cx - r * .6, cy - r * .6, cx + r * .6, cy + r * .6), outline=(226, 120, 100), width=int(1.6 * u))
    d.polygon([(cx, cy - 6.5 * u), (cx + 4.5 * u, cy), (cx, cy + 6.5 * u), (cx - 4.5 * u, cy)], fill=(240, 190, 90))
    return im


def main():
    os.makedirs(OUT, exist_ok=True)
    big = draw(1024)
    big.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "app_icon_256.png"))
    big.resize((48, 48), Image.LANCZOS).save(os.path.join(OUT, "app_icon.png"))
    big.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "app_icon.ico"),
                                              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
