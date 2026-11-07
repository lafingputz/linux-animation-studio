"""v0.32 timeline thumbnail correctness and cache invalidation tests."""
import os
import unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QColor, QPainter
    from main import Canvas
    QT = True
except ImportError:
    QT = False

@unittest.skipUnless(QT, 'PySide6 unavailable: run tests in the LAS virtual environment')
class ThumbnailCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.canvas = Canvas()
        self.canvas.reset_document(160, 100)
        self.canvas.frames = [self.canvas.layers]

    def test_repeated_thumbnail_reuses_exact_qimage(self):
        a = self.canvas.frame_thumbnail(0)
        b = self.canvas.frame_thumbnail(0)
        self.assertIs(a, b)
        self.assertEqual(self.canvas.thumbnail_cache_stats()['hits'], 1)

    def test_painting_invalidates_only_changed_frame(self):
        from main import Layer, transparent_image
        import uuid
        other = [Layer(uuid.uuid4().hex, 'Second frame', transparent_image(160, 100))]
        self.canvas.frames.append(other)
        first = self.canvas.frame_thumbnail(0)
        second = self.canvas.frame_thumbnail(1)
        painter = QPainter(self.canvas.frames[0][0].image)
        painter.fillRect(0, 0, 60, 30, QColor('#bb3344'))
        painter.end()
        changed = self.canvas.frame_thumbnail(0)
        still = self.canvas.frame_thumbnail(1)
        self.assertIsNot(first, changed)
        self.assertIs(second, still)

    def test_visibility_and_opacity_invalidate(self):
        layer = self.canvas.frames[0][0]
        first = self.canvas.frame_thumbnail(0)
        layer.visible = False
        second = self.canvas.frame_thumbnail(0)
        self.assertIsNot(first, second)
        layer.visible = True
        layer.opacity = 33
        third = self.canvas.frame_thumbnail(0)
        self.assertIsNot(second, third)

    def test_cache_is_bounded_and_reset(self):
        from main import Layer, transparent_image
        import uuid
        for n in range(119):
            self.canvas.frames.append([Layer(uuid.uuid4().hex, str(n), transparent_image(160, 100))])
        for index in range(120):
            self.canvas.frame_thumbnail(index)
        self.assertLessEqual(self.canvas.thumbnail_cache_stats()['entries'], 128)
        misses = self.canvas.thumbnail_cache_stats()['misses']
        for index in range(120):
            self.canvas.frame_thumbnail(index)
        self.assertEqual(self.canvas.thumbnail_cache_stats()['misses'], misses)
        self.canvas.reset_document(160, 100)
        self.assertEqual(self.canvas.thumbnail_cache_stats()['entries'], 0)

    def test_motion_key_change_invalidates_thumbnail(self):
        from main import MotionObject, transparent_image
        import uuid
        obj = MotionObject(uuid.uuid4().hex, 'Motion', transparent_image(160,100), {0:(0,0,100,0)})
        self.canvas.motion_objects = [obj]
        first = self.canvas.frame_thumbnail(0)
        obj.keys[0] = (12,0,100,0)
        second = self.canvas.frame_thumbnail(0)
        self.assertIsNot(first, second)

if __name__ == '__main__':
    unittest.main()
