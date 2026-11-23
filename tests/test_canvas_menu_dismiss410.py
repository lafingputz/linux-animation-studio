"""v0.41 context menu dismissals must not draw dots or fill pixels."""
import ast
from pathlib import Path
import unittest

SOURCE=(Path(__file__).resolve().parents[1]/'main.py').read_text(encoding='utf-8')
TREE=ast.parse(SOURCE)
def method(cls,name):
    klass=next(n for n in TREE.body if isinstance(n,ast.ClassDef) and n.name==cls)
    func=next(n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name==name)
    return ast.get_source_segment(SOURCE,func)

class PopupDismissClickTests(unittest.TestCase):
    def test_press_is_consumed_before_tool_stroke_or_fill(self):
        code=method('Canvas','mousePressEvent')
        self.assertIn('if self._dismiss_canvas_menu_press and event.button() == Qt.MouseButton.LeftButton:',code)
        self.assertIn('self._dismiss_canvas_menu_mouse_down = True',code)
        self.assertLess(code.index('self._dismiss_canvas_menu_press and'),code.index('self.flood_fill('))
        self.assertLess(code.index('self._dismiss_canvas_menu_press and'),code.index("self._begin_stroke('mouse')"))

    def test_tablet_press_suppressed_before_tool_or_fill(self):
        code=method('Canvas','tabletEvent')
        self.assertIn('typ == QEvent.Type.TabletPress and self._dismiss_canvas_menu_press',code)
        self.assertIn('self._dismiss_canvas_menu_tablet_down = True',code)
        self.assertLess(code.index('typ == QEvent.Type.TabletPress and self._dismiss_canvas_menu_press'),code.index('self.flood_fill('))

    def test_suppressed_gesture_does_not_paint_on_move_or_release(self):
        for method_name in ('mouseMoveEvent','mouseReleaseEvent'):
            self.assertIn('self._dismiss_canvas_menu_mouse_down',method('Canvas',method_name))
        self.assertIn('self._dismiss_canvas_menu_tablet_down',method('Canvas','tabletEvent'))

    def test_selected_actions_restore_normal_canvas_clicks(self):
        code=method('MainWindow','_canvas_context_menu')
        self.assertIn('self.canvas._dismiss_canvas_menu_press = True',code)
        self.assertIn('menu.triggered.connect(action_chosen)',code)
        self.assertIn('chosen_action[0] = True',code)
        self.assertIn('self.canvas._dismiss_canvas_menu_press = False',code)
        self.assertIn('not chosen_action[0]',code)
        self.assertIn("spin.valueChanged.connect(original.setValue)",code)

if __name__=='__main__':
    unittest.main()
