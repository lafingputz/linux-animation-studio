"""Automated .las file format smoke tests (run with a Qt-capable environment)."""
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor
from main import Canvas, PROJECT_VERSION, png_bytes, transparent_image

class ProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def create_legacy(self, path, version):
        ident = uuid.uuid4().hex
        image = transparent_image(16, 12)
        image.fill(QColor('#aa5522'))
        entry = {'id': ident, 'name': 'Old art', 'visible': True, 'opacity': 100,
                 'file': ('layers/' if version == 1 else 'frames/0/') + ident + '.png'}
        if version >= 4:
            entry['mode'] = 'animated'
        if version >= 5:
            entry['cel_id'] = uuid.uuid4().hex
        manifest = {'format': 'linux-animation-studio', 'version': version,
                    'width': 16, 'height': 12, 'active_layer': ident}
        if version == 1:
            manifest['layers'] = [entry]
        else:
            manifest['frames'] = [{'layers': [entry]}]
            manifest['active_frame'] = 0
            manifest['fps'] = 12
        if version >= 3:
            manifest['motion_objects'] = []
        if version >= 6:
            manifest['brush_color'] = '#336699'
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(entry['file'], png_bytes(image))
            archive.writestr('manifest.json', json.dumps(manifest))

    def test_v1_through_v6_open(self):
        with tempfile.TemporaryDirectory() as directory:
            for version in range(1, PROJECT_VERSION + 1):
                with self.subTest(version=version):
                    path = Path(directory) / f'legacy-v{version}.las'
                    self.create_legacy(path, version)
                    canvas = Canvas()
                    canvas.load_project(path)
                    self.assertEqual((canvas.width_px, canvas.height_px), (16, 12))
                    self.assertEqual(len(canvas.layers), 1)
                    self.assertEqual(canvas.layers[0].image.pixelColor(0, 0).name(), '#aa5522')
                    self.assertEqual(canvas.color.name(), '#336699' if version == 6 else '#000000')

    def test_v6_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'roundtrip.las'
            canvas = Canvas()
            canvas.reset_document(32, 24)
            canvas.layers[0].image.fill(QColor('#45aabb'))
            canvas.color = QColor('#123456')
            canvas.save_project(path)
            loaded = Canvas()
            loaded.load_project(path)
            self.assertEqual(loaded.color.name(), '#123456')
            self.assertEqual(loaded.layers[0].image.pixelColor(0, 0).name(), '#45aabb')
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(json.loads(archive.read('manifest.json'))['version'], 6)

    def test_invalid_project_leaves_document_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'invalid.las'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('manifest.json', json.dumps({
                    'format':'linux-animation-studio','version':999,'width':10,'height':10}))
            canvas = Canvas()
            canvas.reset_document(20, 18)
            with self.assertRaises(ValueError):
                canvas.load_project(path)
            self.assertEqual((canvas.width_px, canvas.height_px), (20,18))

if __name__ == '__main__':
    unittest.main()
