"""Guard against orphan strokes after dismissing a nonblocking canvas popup."""
import ast
import unittest
from pathlib import Path

SOURCE=(Path(__file__).resolve().parents[1]/'main.py').read_text(encoding='utf-8')
TREE=ast.parse(SOURCE)

def function_in(cls,name):
    node=next(node for node in TREE.body if isinstance(node,ast.ClassDef) and node.name==cls)
    func=next(node for node in node.body if isinstance(node,ast.FunctionDef) and node.name==name)
    return ast.get_source_segment(SOURCE,func)

class ContextMenuStrokeTests(unittest.TestCase):
    def test_mouse_move_without_pressed_button_finishes_orphan_stroke(self):
        code=function_in('Canvas','mouseMoveEvent')
        self.assertIn("self.input_kind == 'mouse'",code)
        self.assertIn('not (event.buttons() & Qt.MouseButton.LeftButton)',code)
        self.assertIn('self._end_stroke()',code)

    def test_fresh_press_never_joins_orphan_stroke(self):
        code=function_in('Canvas','mousePressEvent')
        self.assertIn("self.input_kind == 'mouse'",code)
        self.assertIn('self._end_stroke()',code)
        self.assertIn("self._begin_stroke('mouse')",code)
        self.assertLess(code.index('self._end_stroke()'),code.index("self._begin_stroke('mouse')"))

    def test_menu_open_and_close_finalize_mouse_strokes(self):
        code=function_in('MainWindow','_canvas_context_menu')
        self.assertIn("self.canvas.input_kind == 'mouse'",code)
        self.assertGreaterEqual(code.count('self.canvas._end_stroke()'),2)
        self.assertIn('menu.aboutToHide.connect(clear_active_menu)',code)

if __name__=='__main__':
    unittest.main()
