"""Regressions for cursor/hover loss after dismissing canvas context menus."""
import ast
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)

def method(cls, name):
    definition = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == cls)
    function = next(n for n in definition.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(SOURCE, function)

class ContextHoverRestorationTests(unittest.TestCase):
    def test_menu_close_schedules_hover_restore(self):
        code = method('MainWindow', '_canvas_context_menu')
        self.assertIn('QTimer.singleShot(0, self._restore_canvas_hover_after_menu)', code)

    def test_restore_cursor_without_any_canvas_click(self):
        code = method('MainWindow', '_restore_canvas_hover_after_menu')
        self.assertIn('self.canvas.refresh_cursor()', code)
        self.assertIn('self.canvas.mapFromGlobal(QCursor.pos())', code)
        self.assertIn('self.canvas.show_hover(', code)
        self.assertNotIn('mousePressEvent(', code)
        self.assertNotIn('self.canvas.stroke(', code)

    def test_swallowed_mouse_release_does_not_strand_hover(self):
        code = method('Canvas', 'mouseMoveEvent')
        self.assertIn('if not (event.buttons() & Qt.MouseButton.LeftButton):', code)
        self.assertIn('self._dismiss_canvas_menu_mouse_down = False', code)
        self.assertIn('self.show_hover(', code)

    def test_tablet_hover_resets_swallowed_release(self):
        code = method('Canvas', 'tabletEvent')
        self.assertIn('typ == QEvent.Type.TabletMove', code)
        self.assertIn('self._dismiss_canvas_menu_tablet_down = False', code)
        self.assertIn('self.show_hover(', code)

    def test_bucket_uses_its_cursor_without_brush_circle(self):
        code = method('Canvas', 'paintEvent')
        self.assertIn("if self.tool in ('brush', 'eraser'):", code)
        self.assertNotIn("if self.tool in ('brush', 'eraser', 'fill'):", code)

if __name__ == '__main__':
    unittest.main()
