#!/usr/bin/env python3
"""
main.py -- make.fun bounty "news-image-20261124"

Renders a single 1024x1024 PNG ($MAKEFUN_OUTPUT_DIR/entry.png, falling back
to /output/entry.png) summarizing world news of 24 November 2026.

Everything below is pure Python 3.13 standard library: no network calls and
no third-party packages. The PNG container is assembled by hand with
`struct` (chunk framing) and `zlib` (DEFLATE compression of the raw
scanlines + CRC32 checksums); there is no image library available at
runtime. Text is rendered with a small embedded 5x7 bitmap font, and the
story icons are simple filled circles / rectangles / triangles drawn with
plain pixel math.

Output is fully deterministic: no randomness, no timestamps, no dict-order
dependence, and zlib.compress() is called with a fixed compresslevel, so
running the script twice produces byte-identical PNGs.
"""

import os
import struct
import zlib

# ---------------------------------------------------------------------------
# Canvas geometry
# ---------------------------------------------------------------------------

WIDTH = 1024
HEIGHT = 1024

COLOR_BG = (10, 14, 33)          # dark navy background
COLOR_TITLE_BAR = (16, 22, 48)   # slightly lighter navy for the title bar
COLOR_CARD_BG = (22, 28, 58)     # card background
COLOR_CARD_BORDER = (46, 54, 92)
COLOR_WHITE = (235, 240, 250)
COLOR_DIM = (150, 165, 200)

# ---------------------------------------------------------------------------
# 5x7 bitmap font. Each glyph is 7 rows of a 5-char string; '#' = lit pixel.
# Covers A-Z, 0-9, space and ". , ' - : $ % /" -- everything the captions
# below use. A self-check at import time guarantees every row is 5 wide and
# every glyph is 7 rows tall, so a typo here fails loudly instead of
# silently corrupting the layout.
# ---------------------------------------------------------------------------

FONT = {
    'A': [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    'B': ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    'C': [".####", "#....", "#....", "#....", "#....", "#....", ".####"],
    'D': ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    'E': ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    'F': ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    'G': [".####", "#....", "#....", "#.###", "#...#", "#...#", ".####"],
    'H': ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    'I': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    'J': ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    'K': ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    'L': ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    'M': ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    'N': ["#...#", "##..#", "#.#.#", "#.#.#", "#..##", "#...#", "#...#"],
    'O': [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    'P': ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    'Q': [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    'R': ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    'S': [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    'T': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    'U': ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    'V': ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    'W': ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    'X': ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    'Y': ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    'Z': ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    '0': [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    '1': ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    '2': [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    '3': [".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###."],
    '4': ["#...#", "#...#", "#...#", "#####", "....#", "....#", "....#"],
    '5': ["#####", "#....", "#....", "####.", "....#", "#...#", ".###."],
    '6': [".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."],
    '7': ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    '8': [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    '9': [".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."],
    ' ': [".....", ".....", ".....", ".....", ".....", ".....", "....."],
    '.': [".....", ".....", ".....", ".....", ".....", ".....", "..#.."],
    ',': [".....", ".....", ".....", ".....", ".....", "..#..", ".#..."],
    "'": [".#...", ".#...", ".....", ".....", ".....", ".....", "....."],
    '-': [".....", ".....", ".....", ".###.", ".....", ".....", "....."],
    ':': [".....", "..#..", ".....", ".....", "..#..", ".....", "....."],
    '$': ["..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#.."],
    '%': ["#...#", "#..#.", "...#.", "..#..", ".#...", ".#..#", "#...#"],
    '/': ["....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."],
}

for _ch, _rows in FONT.items():
    assert len(_rows) == 7, f"glyph {_ch!r} must have 7 rows"
    for _row in _rows:
        assert len(_row) == 5, f"glyph {_ch!r} row {_row!r} must be 5 wide"

FONT_GLYPH_W = 5
FONT_GLYPH_H = 7
FONT_ADVANCE = FONT_GLYPH_W + 1  # 1px of inter-character spacing


# ---------------------------------------------------------------------------
# Minimal RGB canvas + hand-rolled PNG encoder (struct + zlib only)
# ---------------------------------------------------------------------------

class Canvas:
    def __init__(self, width, height, bg):
        self.width = width
        self.height = height
        self.buf = bytearray(bg * (width * height))

    def set_px(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            i = (y * self.width + x) * 3
            self.buf[i] = color[0]
            self.buf[i + 1] = color[1]
            self.buf[i + 2] = color[2]

    def fill_rect(self, x, y, w, h, color):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + w), min(self.height, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            i0 = (yy * self.width + x0) * 3
            self.buf[i0:i0 + len(row)] = row

    def rect_outline(self, x, y, w, h, color, thickness=2):
        self.fill_rect(x, y, w, thickness, color)
        self.fill_rect(x, y + h - thickness, w, thickness, color)
        self.fill_rect(x, y, thickness, h, color)
        self.fill_rect(x + w - thickness, y, thickness, h, color)

    def fill_circle(self, cx, cy, r, color):
        r2 = r * r
        for yy in range(cy - r, cy + r + 1):
            if yy < 0 or yy >= self.height:
                continue
            dy2 = (yy - cy) ** 2
            if dy2 > r2:
                continue
            dx = int((r2 - dy2) ** 0.5)
            x0, x1 = max(0, cx - dx), min(self.width, cx + dx + 1)
            if x1 <= x0:
                continue
            row = bytes(color) * (x1 - x0)
            i0 = (yy * self.width + x0) * 3
            self.buf[i0:i0 + len(row)] = row

    def circle_outline(self, cx, cy, r, color, thickness=2):
        self.fill_circle(cx, cy, r, color)
        self.fill_circle(cx, cy, r - thickness, COLOR_CARD_BG)

    def fill_triangle(self, p0, p1, p2, color):
        xs = (p0[0], p1[0], p2[0])
        ys = (p0[1], p1[1], p2[1])
        x0, x1 = max(0, min(xs)), min(self.width, max(xs) + 1)
        y0, y1 = max(0, min(ys)), min(self.height, max(ys) + 1)

        def sign(ax, ay, bx, by, cx, cy):
            return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

        for yy in range(y0, y1):
            for xx in range(x0, x1):
                d1 = sign(xx, yy, *p0, *p1)
                d2 = sign(xx, yy, *p1, *p2)
                d3 = sign(xx, yy, *p2, *p0)
                has_neg = d1 < 0 or d2 < 0 or d3 < 0
                has_pos = d1 > 0 or d2 > 0 or d3 > 0
                if not (has_neg and has_pos):
                    self.set_px(xx, yy, color)

    def draw_char(self, ch, x, y, color, scale):
        glyph = FONT.get(ch.upper(), FONT[' '])
        for ry, row in enumerate(glyph):
            for rx, bit in enumerate(row):
                if bit == '#':
                    self.fill_rect(x + rx * scale, y + ry * scale, scale, scale, color)

    def draw_text(self, text, x, y, color, scale):
        cx = x
        for ch in text:
            self.draw_char(ch, cx, y, color, scale)
            cx += FONT_ADVANCE * scale

    def to_png_bytes(self):
        row_bytes = self.width * 3
        raw = bytearray()
        for yy in range(self.height):
            raw.append(0)  # filter type 0 (none) per scanline
            start = yy * row_bytes
            raw.extend(self.buf[start:start + row_bytes])
        compressed = zlib.compress(bytes(raw), 9)

        def chunk(tag, data):
            return (
                struct.pack('>I', len(data))
                + tag
                + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)
            )

        sig = b'\x89PNG\r\n\x1a\n'
        ihdr = struct.pack('>IIBBBBB', self.width, self.height, 8, 2, 0, 0, 0)
        return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', compressed) + chunk(b'IEND', b'')


# ---------------------------------------------------------------------------
# Text width helper -- used BEFORE captions are written, to cap line length
# ---------------------------------------------------------------------------

def max_chars_for_width(px_width, scale):
    """How many font characters fit in px_width at the given scale.

    Used BEFORE any caption string is written below, so every card's text
    budget is known ahead of time instead of guessed and checked by eye.
    """
    return px_width // (FONT_ADVANCE * scale)


def text_width(text, scale):
    return len(text) * FONT_ADVANCE * scale


# ---------------------------------------------------------------------------
# Story content -- 24 November 2026 world news, six stories, good breadth:
# Gulf/maritime security, NATO-Russia escalation, US tech/corporate,
# UN diplomacy, child-casualty humanitarian, African conflict.
# ---------------------------------------------------------------------------

CARDS = [
    {
        "title": "HORMUZ TANKERS",
        "lines": [
            "IRGC NAVY: MINE BLASTS",
            "SET 3 OIL TANKERS",
            "ABLAZE NEAR HORMUZ",
        ],
        "accent": (255, 140, 40),
        "icon": "hormuz",
    },
    {
        "title": "RUSSIA, ESTONIA",
        "lines": [
            "MOSCOW WARNS OF OPEN",
            "WAR AFTER NATO MEMBER",
            "SHUTS RUSSIA BORDER",
        ],
        "accent": (235, 60, 60),
        "icon": "estonia",
    },
    {
        "title": "NVIDIA CEO SAGA",
        "lines": [
            "TRUMP HELPS RESTORE",
            "JENSEN HUANG AS CEO",
            "DAYS AFTER OUSTER",
        ],
        "accent": (60, 200, 110),
        "icon": "nvidia",
    },
    {
        "title": "UN SECURITY",
        "lines": [
            "RUSSIA, UKRAINE CLASH",
            "OVER BLACK SEA SHIPS",
            "MOSCOW RULES OUT DEAL",
        ],
        "accent": (70, 150, 235),
        "icon": "un",
    },
    {
        "title": "UNICEF: TOLL",
        "lines": [
            "3 KIDS KILLED OR HURT",
            "DAILY IN UKRAINE WAR",
            "HIGHEST SINCE 2022",
        ],
        "accent": (210, 90, 200),
        "icon": "unicef",
    },
    {
        "title": "SUDAN DRONES",
        "lines": [
            "DRONE ATTACK HITS",
            "KHARTOUM AS POWER",
            "GRID NEARS COLLAPSE",
        ],
        "accent": (235, 190, 50),
        "icon": "sudan",
    },
]

TITLE_TEXT = "WORLD NEWS"
DATE_TEXT = "24 NOVEMBER 2026"

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

MARGIN = 24
TITLE_BAR_H = 110
GRID_GAP = 20
COLS = 3
ROWS = 2

GRID_TOP = TITLE_BAR_H + MARGIN
grid_width = WIDTH - 2 * MARGIN
grid_height = HEIGHT - GRID_TOP - MARGIN
CARD_W = (grid_width - (COLS - 1) * GRID_GAP) // COLS
CARD_H = (grid_height - (ROWS - 1) * GRID_GAP) // ROWS

CARD_PAD = 18
ICON_AREA = 64            # square icon reserved at top of each card
TITLE_SCALE = 3
CAPTION_SCALE = 2
LINE_GAP = 6              # extra px between caption lines

# Text area width available inside a card, accounting for left/right padding
TEXT_AREA_W = CARD_W - 2 * CARD_PAD

MAX_TITLE_CHARS = max_chars_for_width(TEXT_AREA_W, TITLE_SCALE)
MAX_CAPTION_CHARS = max_chars_for_width(TEXT_AREA_W, CAPTION_SCALE)

# Hard self-check: every caption/title string must fit the computed budget.
# This runs every time the script executes (part of the deterministic
# output path), so a layout regression fails loudly instead of silently
# overflowing a card.
for _card in CARDS:
    assert len(_card["title"]) <= MAX_TITLE_CHARS, (
        f"title too long: {_card['title']!r} "
        f"({len(_card['title'])} > {MAX_TITLE_CHARS} chars)"
    )
    for _line in _card["lines"]:
        assert len(_line) <= MAX_CAPTION_CHARS, (
            f"caption line too long: {_line!r} "
            f"({len(_line)} > {MAX_CAPTION_CHARS} chars)"
        )
        for _c in _line:
            assert _c.upper() in FONT, f"character {_c!r} not in FONT dict"


# ---------------------------------------------------------------------------
# Icon drawing -- small geometric glyphs, one style per story
# ---------------------------------------------------------------------------

def draw_icon(canvas, kind, x, y, size, color):
    """Draw a simple circle/rect/triangle icon inside the x,y,size box."""
    cx, cy = x + size // 2, y + size // 2
    r = size // 2 - 4

    if kind == "hormuz":
        # mine (circle with cross) above a ship hull (rect + triangle bow)
        canvas.fill_circle(cx, y + size // 3, r // 2, color)
        canvas.fill_rect(cx - r, y + size // 3 - 2, r * 2, 4, COLOR_CARD_BG)
        canvas.fill_rect(cx - 2, y + size // 3 - r, 4, r * 2, COLOR_CARD_BG)
        canvas.fill_rect(x + 6, y + size - 20, size - 12, 12, color)
        canvas.fill_triangle(
            (x + 6, y + size - 20),
            (x + size - 6, y + size - 20),
            (cx, y + size - 32),
            color,
        )
    elif kind == "estonia":
        # warning triangle with exclamation bar
        canvas.fill_triangle(
            (cx, y + 6), (x + 8, y + size - 8), (x + size - 8, y + size - 8), color
        )
        canvas.fill_rect(cx - 3, y + size // 2 - 4, 6, 14, COLOR_CARD_BG)
        canvas.fill_rect(cx - 3, y + size - 16, 6, 6, COLOR_CARD_BG)
    elif kind == "nvidia":
        # chip: rect with pin rects around it
        chip = size - 24
        canvas.fill_rect(x + 12, y + 12, chip, chip, color)
        canvas.fill_rect(x + 12 + 8, y + 12 + 8, chip - 16, chip - 16, COLOR_CARD_BG)
        for i in range(3):
            px = x + 20 + i * ((chip - 16) // 2)
            canvas.fill_rect(px, y + 4, 6, 8, color)
            canvas.fill_rect(px, y + size - 12, 6, 8, color)
    elif kind == "un":
        # globe: circle with horizontal + vertical bands
        canvas.fill_circle(cx, cy, r, color)
        canvas.fill_circle(cx, cy, r - 8, COLOR_CARD_BG)
        canvas.fill_rect(cx - r + 8, cy - 3, (r - 8) * 2, 6, color)
        canvas.fill_rect(cx - 3, cy - r + 8, 6, (r - 8) * 2, color)
    elif kind == "unicef":
        # small figure: circle head + triangle body (child motif)
        canvas.fill_circle(cx, y + size // 3, r // 2, color)
        canvas.fill_triangle(
            (cx - r // 2, y + size - 8),
            (cx + r // 2, y + size - 8),
            (cx, y + size // 3 + 6),
            color,
        )
    elif kind == "sudan":
        # building silhouette with a broken roofline + drone triangle
        canvas.fill_rect(x + 10, y + size // 2, size - 20, size // 2 - 6, color)
        for i in range(3):
            wx = x + 18 + i * 14
            canvas.fill_rect(wx, y + size // 2 + 8, 6, 8, COLOR_CARD_BG)
        canvas.fill_triangle(
            (x + 10, y + 10), (x + size - 10, y + 6), (x + size - 20, y + size // 2 - 4),
            color,
        )
    else:
        canvas.fill_circle(cx, cy, r, color)


# ---------------------------------------------------------------------------
# Compose the full image
# ---------------------------------------------------------------------------

def render():
    c = Canvas(WIDTH, HEIGHT, COLOR_BG)

    # Title bar
    c.fill_rect(0, 0, WIDTH, TITLE_BAR_H, COLOR_TITLE_BAR)
    c.fill_rect(0, TITLE_BAR_H - 4, WIDTH, 4, (90, 110, 180))
    title_scale = 6
    date_scale = 3
    title_w = text_width(TITLE_TEXT, title_scale)
    c.draw_text(TITLE_TEXT, (WIDTH - title_w) // 2, 22, COLOR_WHITE, title_scale)
    date_w = text_width(DATE_TEXT, date_scale)
    c.draw_text(DATE_TEXT, (WIDTH - date_w) // 2, 72, COLOR_DIM, date_scale)

    # Story cards, 3 columns x 2 rows
    for idx, card in enumerate(CARDS):
        row = idx // COLS
        col = idx % COLS
        x = MARGIN + col * (CARD_W + GRID_GAP)
        y = GRID_TOP + row * (CARD_H + GRID_GAP)

        c.fill_rect(x, y, CARD_W, CARD_H, COLOR_CARD_BG)
        c.rect_outline(x, y, CARD_W, CARD_H, COLOR_CARD_BORDER, thickness=2)
        # accent bar along the top edge of the card
        c.fill_rect(x, y, CARD_W, 8, card["accent"])

        icon_x = x + (CARD_W - ICON_AREA) // 2
        icon_y = y + 18
        draw_icon(c, card["icon"], icon_x, icon_y, ICON_AREA, card["accent"])

        text_x = x + CARD_PAD
        title_y = icon_y + ICON_AREA + 14
        c.draw_text(card["title"], text_x, title_y, COLOR_WHITE, TITLE_SCALE)

        line_y = title_y + FONT_GLYPH_H * TITLE_SCALE + 14
        line_step = FONT_GLYPH_H * CAPTION_SCALE + LINE_GAP
        for line in card["lines"]:
            c.draw_text(line, text_x, line_y, COLOR_DIM, CAPTION_SCALE)
            line_y += line_step

    return c


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "entry.png")

    canvas = render()
    png_bytes = canvas.to_png_bytes()

    with open(out_path, "wb") as f:
        f.write(png_bytes)


if __name__ == "__main__":
    main()
