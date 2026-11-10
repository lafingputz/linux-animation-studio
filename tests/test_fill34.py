"""Qt-independent flood-fill algorithm checks and optional Qt integration tests."""
import ast
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fill_support import flood_region

class FloodRegionTests(unittest.TestCase):
    def test_enclosed_region_and_border(self):
        white=0xFFFFFFFF; black=0xFF000000
        values=[white]*25
        for i in range(5):
            values[i]=values[20+i]=values[i*5]=values[i*5+4]=black
        region=flood_region(values,5,5,2,2,0)
        self.assertEqual(sum(region),9)
        self.assertEqual(region[0],0)
        self.assertEqual(region[12],1)

    def test_contiguous_vs_global(self):
        white=0xFFFFFFFF; black=0xFF000000
        pixels=[white,white,black,white,white]
        self.assertEqual(sum(flood_region(pixels,5,1,0,0)),2)
        self.assertEqual(sum(flood_region(pixels,5,1,0,0,contiguous=False)),4)

    def test_tolerance(self):
        pixels=[0xFF303030,0xFF383838,0xFF666666]
        self.assertEqual(sum(flood_region(pixels,3,1,0,0,7)),1)
        self.assertEqual(sum(flood_region(pixels,3,1,0,0,8)),2)

    def test_alpha_and_transparent_rgb(self):
        pixels=[0x00000000,0x00ABCDEF,0xFF000000]
        self.assertEqual(sum(flood_region(pixels,3,1,0,0,0)),2)

    def test_selection_is_barrier(self):
        pixels=[0xFFFFFFFF]*9
        allowed=bytearray([1,1,1,0,0,0,1,1,1])
        self.assertEqual(sum(flood_region(pixels,3,3,1,0,allowed=allowed)),3)
        self.assertEqual(sum(flood_region(pixels,3,3,1,1,allowed=allowed)),0)

    def test_invalid_and_off_canvas(self):
        self.assertEqual(sum(flood_region([0],1,1,-1,0)),0)
        with self.assertRaises(ValueError):
            flood_region([0],3,3,0,0)

    def test_source_hooks(self):
        source=(ROOT/'main.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('APP_VERSION = "0.35.0"',source)
        for needle in ["('fill', '🪣'", "('Paint Bucket Tool', 'G'",'def flood_fill(self, position):',"elif self.tool in ('brush', 'eraser')",'from fill_support import flood_region', 'def bucket_cursor():', 'def draw_bucket_glyph(']:
            self.assertIn(needle,source)

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QColor, QPainter, QPainterPath
    from PySide6.QtCore import QPointF, QRect
    from main import Canvas
    QT=True
except ImportError:
    QT=False

@unittest.skipUnless(QT,'Install PySide6 to run UI raster integration tests')
class FloodQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.canvas=Canvas()
        self.canvas.reset_document(32,24)
        self.canvas.color=QColor('#00AA55')
        self.canvas.fill_tolerance=0

    def outline(self):
        layer=self.canvas.active_layer()
        painter=QPainter(layer.image)
        painter.fillRect(QRect(2,2,16,16),QColor('black'))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(QRect(3,3,14,14),QColor('transparent'))
        painter.end()

    def test_bucket_undo_redo(self):
        self.outline()
        self.assertTrue(self.canvas.flood_fill(QPointF(6,6)))
        self.assertEqual(self.canvas.active_layer().image.pixelColor(6,6).name(),'#00aa55')
        self.assertEqual(self.canvas.active_layer().image.pixelColor(2,2).name(),'#000000')
        self.assertEqual(self.canvas.active_layer().image.pixelColor(22,20).alpha(),0)
        self.canvas.undo()
        self.assertEqual(self.canvas.active_layer().image.pixelColor(6,6).alpha(),0)
        self.canvas.redo()
        self.assertEqual(self.canvas.active_layer().image.pixelColor(6,6).name(),'#00aa55')

    def test_selection_protects_outside(self):
        self.canvas.set_selection(QRect(0,0,10,10))
        self.assertTrue(self.canvas.flood_fill(QPointF(2,2)))
        self.assertEqual(self.canvas.active_layer().image.pixelColor(2,2).alpha(),255)
        self.assertEqual(self.canvas.active_layer().image.pixelColor(20,20).alpha(),0)
        self.assertFalse(self.canvas.flood_fill(QPointF(15,15)))

    def test_linked_cels(self):
        self.canvas.add_frame(True)
        a,b=self.canvas.frames[0][0],self.canvas.frames[1][0]
        b.cel_id=a.cel_id; b.image=a.image
        self.assertTrue(self.canvas.flood_fill(QPointF(4,4)))
        self.assertEqual(self.canvas.frames[0][0].image.pixelColor(4,4).alpha(),255)
        self.canvas.undo()
        self.assertEqual(self.canvas.frames[1][0].image.pixelColor(4,4).alpha(),0)

    def test_multiframe_opt_in(self):
        self.canvas.add_frame(True)
        self.canvas.change_frame(0)
        self.canvas.multi_edit_frames=[0,1]
        self.canvas.multi_edit_enabled=False
        self.assertTrue(self.canvas.flood_fill(QPointF(4,4)))
        self.assertEqual(self.canvas.frames[0][0].image.pixelColor(4,4).alpha(),255)
        self.assertEqual(self.canvas.frames[1][0].image.pixelColor(4,4).alpha(),0)
        self.canvas.undo()
        self.canvas.multi_edit_enabled=True
        self.assertTrue(self.canvas.flood_fill(QPointF(4,4)))
        self.assertEqual(self.canvas.frames[0][0].image.pixelColor(4,4).alpha(),255)
        self.assertEqual(self.canvas.frames[1][0].image.pixelColor(4,4).alpha(),255)

if __name__=='__main__': unittest.main()
