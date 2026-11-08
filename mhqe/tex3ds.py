"""Decoder for MT Framework 3DS .tex (v0xA5) textures: ETC1 / ETC1A4 / RGBA8 / RGBA4 / RGB565 / A8 / L8 / LA8."""
import struct
from PIL import Image
MOD = [(2, 8), (5, 17), (9, 29), (13, 42), (18, 60), (24, 80), (33, 106), (47, 183)]
def _c(v): return 0 if v < 0 else 255 if v > 255 else v
def etc1_block(word):
    hi = word >> 32
    diff = (hi >> 1) & 1; flip = hi & 1
    t1 = (hi >> 5) & 7; t2 = (hi >> 2) & 7
    if diff:
        def s3(v): return v - 8 if v & 4 else v
        r1, g1, b1 = (hi >> 27) & 31, (hi >> 19) & 31, (hi >> 11) & 31
        r2, g2, b2 = r1 + s3((hi >> 24) & 7), g1 + s3((hi >> 16) & 7), b1 + s3((hi >> 8) & 7)
        e = lambda v: (v << 3) | (v >> 2)
        c1 = (e(r1), e(g1), e(b1)); c2 = (e(r2 & 31), e(g2 & 31), e(b2 & 31))
    else:
        c1 = tuple(((hi >> s) & 15) * 17 for s in (28, 20, 12))
        c2 = tuple(((hi >> s) & 15) * 17 for s in (24, 16, 8))
    lo = word & 0xFFFFFFFF
    px = [[None] * 4 for _ in range(4)]
    for x in range(4):
        for y in range(4):
            i = x * 4 + y
            idx = ((lo >> (16 + i)) & 1) << 1 | ((lo >> i) & 1)
            first = (y < 2) if flip else (x < 2)
            base = c1 if first else c2
            a, b = MOD[t1 if first else t2]
            m = (a, b, -a, -b)[idx]
            px[y][x] = (_c(base[0] + m), _c(base[1] + m), _c(base[2] + m))
    return px
def decode(data):
    assert data[:4] == b'TEX\0', data[:4]
    b1, b2, b3 = struct.unpack_from('<III', data, 4)
    w = (b2 >> 6) & 0x1FFF; h = (b2 >> 19) & 0x1FFF; fmt = (b3 >> 8) & 0xFF
    pix = data[0x14:]
    img = Image.new('RGBA', (w, h))
    put = img.putpixel
    if fmt in (0x0B, 0x0C):
        bs = 16 if fmt == 0x0C else 8
        off = 0
        for ty in range(0, h, 8):
            for tx in range(0, w, 8):
                for bx, by in ((0, 0), (4, 0), (0, 4), (4, 4)):
                    if fmt == 0x0C:
                        alpha = struct.unpack_from('<Q', pix, off)[0]; col = struct.unpack_from('<Q', pix, off + 8)[0]
                    else:
                        alpha = None; col = struct.unpack_from('<Q', pix, off)[0]
                    off += bs
                    blk = etc1_block(col)
                    for y in range(4):
                        for x in range(4):
                            a = ((alpha >> ((x * 4 + y) * 4)) & 15) * 17 if alpha is not None else 255
                            r, g, b = blk[y][x]
                            put((tx + bx + x, ty + by + y), (r, g, b, a))
        return img, fmt
    # tiled linear formats (8x8 tiles, Z-order inside)
    bpp = {0x01: 2, 0x02: 4, 0x03: 2, 0x04: 1, 0x05: 1, 0x07: 2}.get(fmt)
    if bpp is None:
        raise ValueError(f'unsupported format 0x{fmt:02X}')
    def z(i):
        x = y = 0
        for bit in range(3):
            x |= ((i >> (2 * bit)) & 1) << bit; y |= ((i >> (2 * bit + 1)) & 1) << bit
        return x, y
    off = 0
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            for i in range(64):
                x, y = z(i)
                v = pix[off:off + bpp]; off += bpp
                if fmt == 0x02: a, b, g, r = v
                elif fmt == 0x01:
                    u = v[0] | v[1] << 8; r, g, b, a = ((u >> 12) & 15) * 17, ((u >> 8) & 15) * 17, ((u >> 4) & 15) * 17, (u & 15) * 17
                elif fmt == 0x03:
                    u = v[0] | v[1] << 8; r, g, b, a = ((u >> 11) & 31) * 255 // 31, ((u >> 5) & 63) * 255 // 63, (u & 31) * 255 // 31, 255
                elif fmt == 0x04: r = g = b = 255; a = v[0]
                elif fmt == 0x05: r = g = b = v[0]; a = 255
                else: a, r = v[0], v[1]; g = b = r
                put((tx + x, ty + y), (r, g, b, a))
    return img, fmt
