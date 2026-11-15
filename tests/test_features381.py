"""Regression checks for v0.38.1 UI and dimension math."""
import unittest
from pathlib import Path
from project_setup import resize_linked_dimension

ROOT = Path(__file__).resolve().parents[1]

class AspectLockTests(unittest.TestCase):
    def test_default_ratio(self):
        self.assertEqual(resize_linked_dimension('width', 2400, 1.5), (2400,1600))
        self.assertEqual(resize_linked_dimension('height', 400, 1.5), (600,400))

    def test_fractional_ratio(self):
        self.assertEqual(resize_linked_dimension('width',1920,16/9),(1920,1080))

    def test_limits(self):
        w,h = resize_linked_dimension('width',999999, 3/2)
        self.assertTrue(1<=w<=16384 and 1<=h<=16384)
        self.assertLessEqual(abs(w/h-1.5),0.001)

    def test_bad_inputs(self):
        with self.assertRaises(ValueError): resize_linked_dimension('depth', 100, 1.5)
        with self.assertRaises(ValueError): resize_linked_dimension('width', 100, 0)

    def test_gui_wiring(self):
        src=(ROOT/'main.py').read_text()
        self.assertIn('self.aspect_lock.setChecked(True)',src)
        self.assertIn("self._dimensions_changed('width')",src)
        self.assertIn("self._dimensions_changed('height')",src)
        self.assertIn("self._aspect_ratio = self._pixel_width /",src)

    def test_accent_updates(self):
        src=(ROOT/'main.py').read_text()
        self.assertIn("b.setObjectName('LASToolSelectionButton')",src)
        self.assertIn('QToolButton#LASToolSelectionButton:checked',src)
        self.assertIn('background-color: {accent}',src)
