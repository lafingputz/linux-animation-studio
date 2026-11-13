"""Selection clearing and linked-cel regression tests for v0.35.1."""
import os
import unittest
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QColor, QPainter, QPainterPath
    from PySide6.QtCore import QRect, QPointF
    from main import Canvas
    HAS_QT = True
except ImportError:
    HAS_QT = False

class ClearSourceTests(unittest.TestCase):
    def test_hooks_and_version(self):
        source = (ROOT / 'main.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        self.assertIn('APP_VERSION = "0.35.1"', source)
        self.assertIn('PROJECT_VERSION = 6', source)
        for phrase in ("('Clear Selected Pixels', 'Delete'",
                       "('Clear Selected Pixels Alternative', 'Backspace'",
                       "editmenu.addAction('Clear Active Cel / Layer'",
                       'def clear_selected_pixels(self):',
                       'def clear_active_cel(self):',
                       "elif typ == 'cel_clear':"):
            self.assertIn(phrase, source)

@unittest.skipUnless(HAS_QT, 'PySide6 unavailable: run in LAS virtual environment')
class ClearQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.canvas = Canvas()
        self.canvas.reset_document(64, 48)

    def paint_all(self, frame=0):
        layer = self.canvas.frames[frame][0]
        p = QPainter(layer.image)
        p.fillRect(layer.image.rect(), QColor('red'))
        p.end()

    def alpha(self, frame, x, y):
        return self.canvas.frames[frame][0].image.pixelColor(x,y).alpha()

    def test_delete_requires_selection_and_supports_undo_redo(self):
        self.paint_all()
        self.assertFalse(self.canvas.clear_selected_pixels())
        self.assertEqual(self.alpha(0, 8, 8), 255)
        self.canvas.set_selection(QRect(3, 3, 10, 10))
        self.assertTrue(self.canvas.clear_selected_pixels())
        self.assertEqual(self.alpha(0, 8, 8), 0)
        self.assertEqual(self.alpha(0, 20, 20), 255)
        self.canvas.undo()
        self.assertEqual(self.alpha(0, 8, 8), 255)
        self.canvas.redo()
        self.assertEqual(self.alpha(0, 8, 8), 0)

    def test_clear_entire_active_cel_ignores_selection(self):
        self.paint_all()
        self.canvas.set_selection(QRect(0,0,4,4))
        self.assertTrue(self.canvas.clear_active_cel())
        self.assertEqual(self.alpha(0, 50, 30), 0)
        self.canvas.undo()
        self.assertEqual(self.alpha(0, 50, 30), 255)

    def test_freehand_selection_clips_clear(self):
        self.paint_all()
        path=QPainterPath(QPointF(4,4))
        path.lineTo(40,4)
        path.lineTo(4,40)
        path.closeSubpath()
        self.canvas.set_selection_path(path)
        self.assertTrue(self.canvas.clear_selected_pixels())
        self.assertEqual(self.alpha(0, 9, 9), 0)
        self.assertEqual(self.alpha(0, 35, 35), 255)

    def test_linked_exposures_clear_and_restore_together(self):
        self.paint_all()
        self.canvas.add_frame(True)
        a,b = self.canvas.frames[0][0], self.canvas.frames[1][0]
        # Make an explicit exposure link regardless of duplicate-frame behavior.
        b.cel_id = a.cel_id
        b.image = a.image
        self.canvas.change_frame(1)
        self.canvas.set_selection(QRect(0,0,12,12))
        self.assertTrue(self.canvas.clear_selected_pixels())
        self.assertEqual(self.alpha(0,5,5),0)
        self.assertEqual(self.alpha(1,5,5),0)
        self.canvas.undo()
        self.assertEqual(self.alpha(0,5,5),255)
        self.assertEqual(self.alpha(1,5,5),255)
        self.canvas.redo()
        self.assertEqual(self.alpha(0,5,5),0)
        self.assertEqual(self.alpha(1,5,5),0)

    def test_unlinked_frames_untouched(self):
        self.paint_all()
        self.canvas.add_frame(True)
        self.canvas.change_frame(1)
        self.assertTrue(self.canvas.clear_active_cel())
        self.assertEqual(self.alpha(0, 3, 3), 255)
        self.assertEqual(self.alpha(1, 3, 3), 0)

    def test_multiframe_edit_explicit_opt_in(self):
        self.paint_all()
        self.canvas.add_frame(True)
        self.canvas.change_frame(0)
        self.canvas.multi_edit_frames=[0,1]
        self.canvas.multi_edit_enabled=True
        self.assertTrue(self.canvas.clear_active_cel())
        self.assertEqual(self.alpha(0, 3, 3),0)
        self.assertEqual(self.alpha(1, 3, 3),0)
        self.canvas.undo()
        self.assertEqual(self.alpha(0, 3, 3),255)
        self.assertEqual(self.alpha(1, 3, 3),255)

    def test_static_layer_clears_all_frames(self):
        self.paint_all()
        self.canvas.add_frame(True)
        self.canvas.set_layer_mode('static')
        self.assertTrue(self.canvas.clear_active_cel())
        self.assertEqual(self.alpha(0, 10, 10),0)
        self.assertEqual(self.alpha(1, 10, 10),0)
        self.canvas.undo()
        self.assertEqual(self.alpha(0, 10, 10),255)
        self.assertEqual(self.alpha(1, 10, 10),255)

if __name__ == '__main__':
    unittest.main()
