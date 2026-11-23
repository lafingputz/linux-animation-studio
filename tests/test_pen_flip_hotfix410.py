"""Phase 2 Windows fix regressions (source-level, hardware verification still required)."""
import ast
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)

def method(klass, name):
    cls = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == klass)
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(SOURCE, node)

class PenFlipRegressionTests(unittest.TestCase):
    def test_manual_keyboard_and_toolbar_selection_never_blocked(self):
        source = method('MainWindow', 'set_tool')
        self.assertIn('self.canvas._tablet_eraser_active = False', source)
        self.assertIn('self._tablet_previous_tool = None', source)
        self.assertIn('self.canvas.change_tool(tool)', source)
        self.assertNotIn('self._tablet_previous_tool = tool\n            return', source)

    def test_mouse_can_restore_last_tool_without_synthetic_pen_event(self):
        source = method('Canvas', 'mousePressEvent')
        self.assertIn('MouseEventNotSynthesized', source)
        self.assertIn('self.tablet_eraser_changed.emit(False)', source)
        self.assertIn("self._begin_stroke('mouse')", source)
        self.assertIn('not self.ignore_mouse', source)

    def test_pipette_icon_is_painted_and_refreshed(self):
        self.assertIn("elif tool == 'eyedropper':\n            # An unmistakable diagonal pipette", SOURCE)
        self.assertIn("('brush', 'eraser', 'fill', 'eyedropper', 'select')", SOURCE)
        self.assertIn("button.setToolTip('Eyedropper: sample the canvas color (I)')", SOURCE)
        self.assertIn('painter.drawRoundedRect(QRectF(-4.5, -11, 9, 17)', SOURCE)

if __name__ == '__main__':
    unittest.main()
