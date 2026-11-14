"""v0.36 source structure checks and optional real Qt integration tests."""
import ast
import os
import sys
import tempfile
import unittest
import zipfile
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

class SourceStructure(unittest.TestCase):
    def test_versions(self):
        source = (ROOT/'main.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('APP_VERSION = "0.37.0"',source)
        self.assertIn('PROJECT_VERSION = 6',source)
        from tools.package_release import VERSION
        self.assertEqual(VERSION,'0.37.0')

    def test_reference_code(self):
        source = (ROOT/'main.py').read_text(encoding='utf-8')
        for fragment in ('def _fill_reference_image(self, frame_index):',
                         'def toggle_reference_layer(self):',
                         "('All visible layers', 'visible')",
                         "('Marked reference layers', 'reference')",
                         "reference=layer.reference",'reference=original.reference',
                         "bool(entry.get('reference', False))"):
            self.assertIn(fragment,source)

    def test_icon_assets(self):
        for ext in ('png','ico','icns'):
            self.assertGreater((ROOT/'assets'/('las.'+ext)).stat().st_size,3000)
        self.assertTrue((ROOT/'assets/spynframe-icon.svg').is_file())

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QColor,QPainter
    from PySide6.QtCore import QPointF,QRect
    from main import Canvas
    QT = True
except ImportError:
    QT = False

@unittest.skipUnless(QT,'Requires PySide6 for GUI integration tests')
class ReferenceFillQt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.canvas = Canvas()
        self.canvas.reset_document(32,24)
        outline = self.canvas.active_layer()
        painter = QPainter(outline.image)
        painter.fillRect(QRect(2,2,18,18), QColor('black'))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(QRect(3,3,16,16), QColor('transparent'))
        painter.end()
        self.outline_id = outline.id
        self.canvas.new_layer()
        self.canvas.color = QColor('#00aa55')

    def test_all_visible_writes_only_active(self):
        self.canvas.fill_source = 'visible'
        self.assertTrue(self.canvas.flood_fill(QPointF(5,5)))
        self.assertEqual(self.canvas.active_layer().image.pixelColor(5,5).name(),'#00aa55')
        self.assertEqual(self.canvas.layer_by_id(self.outline_id).image.pixelColor(5,5).alpha(),0)
        self.assertEqual(self.canvas.active_layer().image.pixelColor(0,0).alpha(),0)
        self.canvas.undo()
        self.assertEqual(self.canvas.active_layer().image.pixelColor(5,5).alpha(),0)

    def test_reference_mode_and_save_load(self):
        self.canvas.fill_source = 'reference'
        self.assertFalse(self.canvas.flood_fill(QPointF(5,5)))
        self.canvas.select_layer(self.outline_id)
        self.canvas.toggle_reference_layer()
        self.canvas.select_layer(self.canvas.layers[-1].id)
        self.assertTrue(self.canvas.flood_fill(QPointF(5,5)))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'reference.las'
            self.canvas.save_project(path)
            with zipfile.ZipFile(path) as z:
                manifest=json.loads(z.read('manifest.json'))
                self.assertEqual(manifest['version'],6)
                self.assertTrue(any(rec['reference'] for rec in manifest['frames'][0]['layers']))
            other=Canvas()
            other.load_project(path)
            self.assertTrue(other.layer_by_id(self.outline_id).reference)

    def test_reference_undo(self):
        self.canvas.select_layer(self.outline_id)
        self.canvas.toggle_reference_layer()
        self.assertTrue(self.canvas.active_layer().reference)
        self.canvas.undo()
        self.assertFalse(self.canvas.active_layer().reference)
        self.canvas.redo()
        self.assertTrue(self.canvas.active_layer().reference)

if __name__=='__main__': unittest.main()
