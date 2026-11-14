"""Qt-independent tests of v0.37.1 conservative boundary-aware expansion."""
import ast
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fill_support import flood_region, expand_region, edge_aware_expand_region


class EdgeAwareFillTests(unittest.TestCase):
    @staticmethod
    def ring(width, height, inside=3, outside=8, opaque=False):
        background = 0xffffffff if opaque else 0
        color = 0xff000000
        values = [background] * (width * height)
        for y in range(height):
            for x in range(width):
                if outside <= x < width-outside or outside <= y < height-outside:
                    continue
                # rectangular line closed around interior
                if inside <= x < width-inside and inside <= y < height-inside:
                    continue
        # a rectangular stroke: interior [inside, width-inside), outer [outside,width-outside)
        for y in range(outside, height-outside):
            for x in range(outside, width-outside):
                if x < inside or x >= width-inside or y < inside or y >= height-inside:
                    values[y*width+x] = color
        return values

    def test_thin_transparent_outline_stays_contained(self):
        w = h = 19
        pixels = [0] * (w*h)
        for y in range(4, 15):
            for x in range(4, 15):
                if x in (4, 14) or y in (4, 14):
                    pixels[y*w+x] = 0xff111111
        region = flood_region(pixels, w, h, 8, 8, 24)
        old = expand_region(region,w,h,8)
        self.assertTrue(old[2*w+8])  # old fill leaks two pixels outside
        new = edge_aware_expand_region(region,pixels,w,h,8,tolerance=24)
        self.assertFalse(new[2*w+8])
        self.assertFalse(new[3*w+8])
        self.assertTrue(new[8*w+8])

    def test_thick_ink_can_accept_safe_internal_fringe(self):
        w=h=25
        pixels=[0]*(w*h)
        for y in range(4,21):
            for x in range(4,21):
                if x<10 or x>14 or y<10 or y>14:
                    pixels[y*w+x]=0xff000000
        region=flood_region(pixels,w,h,12,12,24)
        result=edge_aware_expand_region(region,pixels,w,h,9)
        self.assertTrue(result[9*w+12])
        self.assertFalse(result[4*w+12])
        self.assertFalse(result[3*w+12])

    def test_opaque_white_background_with_dark_outline(self):
        w=h=19
        pixels=[0xffffffff]*(w*h)
        for y in range(4,15):
            for x in range(4,15):
                if x in (4,14) or y in (4,14):
                    pixels[y*w+x]=0xff000000
        region=flood_region(pixels,w,h,8,8,24)
        result=edge_aware_expand_region(region,pixels,w,h,8,tolerance=24)
        self.assertTrue(result[8*w+8])
        self.assertFalse(result[3*w+8])

    def test_selection_never_escaped(self):
        w=h=11
        pixels=[0]*(w*h)
        for y in range(2,9):
            for x in range(2,9):
                if x in (2,8) or y in (2,8): pixels[y*w+x]=0xff000000
        region=flood_region(pixels,w,h,5,5)
        allowed=bytearray([1]*(w*h))
        allowed[4*w+4]=0
        result=edge_aware_expand_region(region,pixels,w,h,5,allowed)
        self.assertFalse(result[4*w+4])

    def test_zero_radius_matches_original(self):
        w=h=5
        region=bytearray(25);region[12]=1
        self.assertEqual(edge_aware_expand_region(region,[0]*25,w,h,0),region)

    def test_source_version_and_controls(self):
        src=(ROOT/'main.py').read_text(encoding='utf-8')
        ast.parse(src)
        self.assertIn('APP_VERSION = "0.37.1"',src)
        for fragment in ('edge_aware_expand_region(', "self.fill_edge_aware = True", "self.fill_opacity = 100", "spin_row('Opacity (%)'", "menu.popup(global_pos)"):
            self.assertIn(fragment,src)
        from tools.package_release import VERSION
        self.assertEqual(VERSION,'0.37.1')

if __name__=='__main__': unittest.main()
