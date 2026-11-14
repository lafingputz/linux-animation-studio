"""Edge expansion regression tests. Pure Python tests run without Qt."""
import random
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fill_support import expand_region, flood_region


def reference_dilation(region, w, h, radius, allowed=None):
    result = bytearray(w*h)
    for y in range(h):
        for x in range(w):
            idx = y*w+x
            if allowed is not None and not allowed[idx]:
                continue
            result[idx] = int(any(region[yy*w+xx] for yy in range(max(0,y-radius),min(h,y+radius+1)) for xx in range(max(0,x-radius),min(w,x+radius+1))))
    return result

class EdgeExpandTests(unittest.TestCase):
    def test_grow_one_pixel_halo(self):
        region=bytearray(7*7)
        region[3*7+3]=1
        expected=reference_dilation(region,7,7,2)
        self.assertEqual(expand_region(region,7,7,2),expected)
        self.assertEqual(sum(expected),25)
        self.assertEqual(sum(region),1)

    def test_no_row_wrap(self):
        region=bytearray(3*4)
        region[2]=1
        grown=expand_region(region,3,4,1)
        self.assertEqual(grown[3],0)
        self.assertEqual(grown[0],0)

    def test_selection_holes_cannot_fill(self):
        region=bytearray(5*5)
        region[12]=1
        selection=bytearray([1]*25)
        selection[13]=0
        grown=expand_region(region,5,5,2,selection)
        self.assertEqual(grown[13],0)
        self.assertEqual(grown[12],1)

    def test_zero_expansion_exact_backward_compatibility(self):
        rng=random.Random(361)
        for _ in range(100):
            w,h=rng.randint(1,15),rng.randint(1,12)
            region=bytearray(rng.randint(0,1) for _ in range(w*h))
            self.assertEqual(expand_region(region,w,h,0),region)

    def test_randomized_against_reference(self):
        rng=random.Random(362)
        for _ in range(160):
            w,h=rng.randint(1,15),rng.randint(1,12)
            r=rng.randint(0,10)
            region=bytearray(rng.randint(0,1) for _ in range(w*h))
            allowed=None if rng.randrange(2) else bytearray(rng.randint(0,1) for _ in region)
            self.assertEqual(expand_region(region,w,h,r,allowed),reference_dilation(region,w,h,r,allowed))

    def test_flood_region_does_not_change_with_expansion(self):
        w=h=7
        pixels=[0]*(w*h)
        for x in range(w): pixels[x]=pixels[(h-1)*w+x]=0xff000000
        for y in range(h):pixels[y*w]=pixels[y*w+w-1]=0xff000000
        core=flood_region(pixels,w,h,3,3,tolerance=24)
        expanded=expand_region(core,w,h,2)
        self.assertEqual(sum(core),25)
        self.assertGreater(sum(expanded),sum(core))

    def test_source_and_package_version(self):
        source=(ROOT/'main.py').read_text(encoding='utf-8')
        self.assertIn('APP_VERSION = "0.36.2"',source)
        self.assertIn('self.fill_expansion = 2',source)
        self.assertIn('expand_region(region, width, height, expansion, selection)',source)
        self.assertIn('CompositionMode_DestinationOver',source)
        from tools.package_release import VERSION
        self.assertEqual(VERSION,'0.36.2')

if __name__=='__main__':unittest.main()
