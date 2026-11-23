"""Wayland canvas popup dismissal should not consume a second click."""
import ast
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)

def method(cls, name):
    klass = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == cls)
    func = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(SOURCE, func)

class WaylandPopupDismissTests(unittest.TestCase):
    def test_menu_armed_before_popup_appears(self):
        code = method("MainWindow", "_canvas_context_menu")
        self.assertLess(code.index("self.canvas._dismiss_canvas_menu_press = True"),
                        code.index("menu.popup(global_pos)"))

    def test_linux_clears_pending_click_after_popup_consumes_dismissal(self):
        code = method("MainWindow", "_canvas_context_menu")
        self.assertIn("if sys.platform.startswith('linux'):", code)
        self.assertIn("self.canvas._dismiss_canvas_menu_press = False", code)
        self.assertIn("elif (not chosen_action[0]", code)
        self.assertLess(code.index("if sys.platform.startswith('linux'):"),
                        code.index("elif (not chosen_action[0]"))

    def test_normal_mouse_and_tablet_gestures_still_have_suppression(self):
        self.assertIn("self._dismiss_canvas_menu_mouse_down = True",
                      method("Canvas", "mousePressEvent"))
        self.assertIn("self._dismiss_canvas_menu_tablet_down = True",
                      method("Canvas", "tabletEvent"))

if __name__ == "__main__":
    unittest.main()
