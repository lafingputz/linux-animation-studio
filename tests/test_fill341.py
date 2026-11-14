"""v0.35.2: optimized region semantics and bucket pointer integration."""
import ast
import random
import sys
import unittest
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fill_support import flood_region


def simple_fill(values, w, h, x, y, tolerance, contiguous, allowed):
    region = bytearray(w * h)
    if not (0 <= x < w and 0 <= y < h) or (allowed is not None and not allowed[y*w+x]):
        return region
    def rgba(value):
        a = value >> 24 & 255
        return (value >> 16 & 255, value >> 8 & 255, value & 255, a) if a else (0,0,0,0)
    target = rgba(values[y*w+x])
    def matches(i):
        return ((allowed is None or allowed[i]) and
                all(abs(a-b) <= tolerance for a,b in zip(rgba(values[i]), target)))
    if not contiguous:
        for i in range(w*h):
            region[i] = int(matches(i))
        return region
    pending = deque([y*w+x])
    while pending:
        i = pending.pop()
        if region[i] or not matches(i):
            continue
        region[i] = 1
        if i%w: pending.append(i-1)
        if i%w < w-1: pending.append(i+1)
        if i>=w: pending.append(i-w)
        if i+w < w*h: pending.append(i+w)
    return region


class Flood341Tests(unittest.TestCase):
    def test_randomized_reference_equivalence(self):
        rng = random.Random(341)
        colors = [0, 0x00ABCDEF, 0xFF223344, 0xFF223345, 0xAA223344, 0xFF888888]
        for _ in range(120):
            w, h = rng.randint(1, 15), rng.randint(1, 12)
            pixels = [rng.choice(colors) for _ in range(w*h)]
            allowed = None if rng.randint(0, 1) else bytearray(rng.randint(0,1) for _ in pixels)
            x, y = rng.randrange(w), rng.randrange(h)
            tolerance = rng.choice((0,1,10,50,255))
            for contiguous in (True, False):
                with self.subTest(w=w,h=h,tolerance=tolerance,contiguous=contiguous):
                    self.assertEqual(flood_region(pixels,w,h,x,y,tolerance,contiguous,allowed),
                                     simple_fill(pixels,w,h,x,y,tolerance,contiguous,allowed))

    def test_bucket_icon_and_true_cursor_hooks(self):
        source = (ROOT/'main.py').read_text(encoding='utf-8')
        ast.parse(source)
        for expected in ("APP_VERSION = \"0.36.0\"", "def draw_bucket_glyph(",
                         "def bucket_cursor():", "return QCursor(pix, 8, 35)",
                         "if self.tool == 'fill':", "for tool in ('brush', 'eraser', 'fill', 'select'):"):
            self.assertIn(expected, source)

    def test_benchmark_is_present(self):
        path = ROOT/'tools'/'benchmark_fill.py'
        self.assertTrue(path.exists())
        ast.parse(path.read_text(encoding='utf-8'))
