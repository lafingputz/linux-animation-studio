"""v0.37.1 canvas navigation regression checks.

These tests validate the implementation's transform geometry when Qt is present.
Source checks still execute in lightweight CI environments without PySide6.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class NavigationSourceTests(unittest.TestCase):
    def test_version_and_no_format_bump(self):
        src = (ROOT / 'main.py').read_text(encoding='utf-8')
        self.assertIn('APP_VERSION = "0.37.1"', src)
        self.assertIn('PROJECT_VERSION = 6', src)
        self.assertIn("VERSION = '0.37.1'", (ROOT / 'tools/package_release.py').read_text(encoding='utf-8'))

    def test_navigation_uses_view_transforms(self):
        src = (ROOT / 'main.py').read_text(encoding='utf-8')
        for text in ('def widget_to_document(', 'def document_to_widget(',
                     'def view_transform(', 'def set_rotation(', 'def zoom_at(',
                     'def rotate_at(', "('zoom', '⌕'", "('rotate', '⟳'",
                     'QEvent.Type.NativeGesture', 'Qt.GestureType.PinchGesture',
                     'def reset_canvas_rotation('):
            with self.subTest(text=text):
                self.assertIn(text, src)
        # No direct division by zoom remains in pointer event handlers.
        mouse = src[src.index('    def tabletEvent('):src.index('    def _copy_layers(', src.index('    def tabletEvent('))]
        self.assertNotIn('event.position() / self.zoom', mouse)
        self.assertIn('self.widget_to_document(event.position())', mouse)

try:
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication
    from main import Canvas, PannableScrollArea
    HAS_QT = True
except ImportError:
    HAS_QT = False

@unittest.skipUnless(HAS_QT, 'PySide6 not installed')
class CanvasNavigationQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_rotated_pixel_round_trip(self):
        canvas = Canvas()
        for zoom in (0.3, 1.0, 2.5):
            canvas.set_zoom(zoom)
            for angle in (0, 15, 45, 90, -135, 179):
                canvas.set_rotation(angle)
                for point in (QPointF(0, 0), QPointF(100, 255),
                              QPointF(600, 400), QPointF(1199, 799)):
                    transformed = canvas.document_to_widget(point)
                    recovered = canvas.widget_to_document(transformed)
                    self.assertAlmostEqual(point.x(), recovered.x(), places=4)
                    self.assertAlmostEqual(point.y(), recovered.y(), places=4)

    def test_bounding_box_expands_at_45_and_normalizes(self):
        canvas = Canvas()
        canvas.set_rotation(45)
        self.assertGreater(canvas.height(), canvas.height_px)
        canvas.set_rotation(360)
        self.assertEqual(canvas.rotation, 0)

    def test_never_changes_layer_pixels_or_project_dirty(self):
        canvas = Canvas()
        before = bytes(canvas.layers[0].image.constBits())
        canvas.set_rotation(30)
        canvas.set_zoom(1.4)
        self.assertEqual(bytes(canvas.layers[0].image.constBits()), before)
        self.assertFalse(canvas.dirty)
