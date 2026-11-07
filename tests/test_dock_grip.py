"""Dependency-free regression checks for the v0.30.1 dock usability fix."""
import ast
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8')

class FloatingDockGripTests(unittest.TestCase):
    def test_wayland_grip_uses_native_system_move(self):
        tree = ast.parse(SOURCE)
        klass = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                     and n.name == 'WaylandFloatingDockHandle')
        mover = next(n for n in klass.body if isinstance(n, ast.FunctionDef)
                     and n.name == 'mousePressEvent')
        segment = ast.get_source_segment(SOURCE, mover)
        self.assertIn('startSystemMove()', segment)
        self.assertNotIn('self.dock.move(', segment)
        self.assertIn('WA_TransparentForMouseEvents', SOURCE)

    def test_wayland_only_and_redock_action(self):
        self.assertIn("'wayland' in QApplication.platformName().lower()", SOURCE)
        self.assertIn("os.environ.get('XDG_SESSION_TYPE'", SOURCE)
        self.assertIn('dock.setTitleBarWidget(None)', SOURCE)
        self.assertIn('redock.clicked.connect(lambda: dock.setFloating(False))', SOURCE)

    def test_native_resize_separators_styled(self):
        self.assertIn('QMainWindow::separator {', SOURCE)
        self.assertIn('width: 9px;', SOURCE)
        self.assertIn('height: 9px;', SOURCE)
        self.assertIn('QMainWindow::separator:hover', SOURCE)

if __name__ == '__main__':
    unittest.main()
