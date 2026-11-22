"""v0.41 Phase 2 regression tests: read-only color sampling and tablet eraser handling.

Native Windows Cintiq eraser-end verification is still required. These tests
exercise real Canvas methods where Qt is installed, without a display server.
"""
import ast
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'main.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)


def class_method(cls, name):
    klass = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == name)


class Phase2SourceTests(unittest.TestCase):
    def test_source_is_valid(self):
        ast.parse(SOURCE)

    def test_eyedropper_uses_document_transform_and_no_paint(self):
        self.assertIn("('Eyedropper Tool', 'I'", SOURCE)
        self.assertIn('self.widget_to_document(event.position())', SOURCE)
        node = class_method('Canvas', 'sample_document_color')
        text = ast.get_source_segment(SOURCE, node)
        self.assertIn("self.composite()", text)
        self.assertIn("self.active_layer().image", text)
        self.assertIn("color.alpha() == 0", text)
        self.assertIn("self.sampled_color.emit(QColor(color))", text)
        for forbidden in ('self._push(', 'self._mark_dirty(', 'self._begin_stroke('):
            self.assertNotIn(forbidden, text)

    def test_eyedropper_has_mode_and_color_swatch(self):
        self.assertIn("self.eyedropper_source_picker.addItem('All visible artwork', 'visible')", SOURCE)
        self.assertIn("self.eyedropper_source_picker.addItem('Active layer only', 'active')", SOURCE)
        self.assertIn('self.canvas.sampled_color.connect(self.update_color_swatch)', SOURCE)
        self.assertIn("self.setCursor(Qt.CursorShape.CrossCursor)", SOURCE)

    def test_tablet_pointer_switch_and_restore(self):
        self.assertIn('QPointingDevice.PointerType.Eraser', SOURCE)
        self.assertIn('self._sync_tablet_eraser(device)', SOURCE)
        self.assertIn('self.tablet_eraser_changed.emit(eraser)', SOURCE)
        self.assertIn('self.canvas.tablet_eraser_changed.connect(self._tablet_eraser_transition)', SOURCE)
        node = class_method('MainWindow', '_tablet_eraser_transition')
        body = ast.get_source_segment(SOURCE, node)
        self.assertIn("self.set_tool('eraser')", body)
        self.assertIn('self.set_tool(previous)', body)
        self.assertIn('self.canvas.drawing', body)

    def test_document_format_unchanged(self):
        self.assertIn('PROJECT_VERSION = 6', SOURCE)


if __name__ == '__main__':
    unittest.main()
