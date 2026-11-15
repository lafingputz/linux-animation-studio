"""v0.38.1: every temporary canvas navigation key is user-configurable."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/'main.py').read_text(encoding='utf-8')

class NavigationKeySourceTests(unittest.TestCase):
    def test_registered_and_persistent_binds(self):
        for entry in (
            "('Temporary / Tap Rotate Tool', 'R', lambda: None)",
            "('Temporary / Tap Zoom Tool', 'Z', lambda: None)",
            "('Temporary Pan', 'Space', lambda: None)",
        ):
            with self.subTest(entry=entry): self.assertIn(entry,SRC)
        self.assertIn("self.preferences.value('shortcuts/' + name, default)",SRC)
        self.assertIn("self.preferences.setValue('shortcuts/' + name, sequence)",SRC)

    def test_runtime_rebind_and_hold_key_release(self):
        self.assertIn('def set_navigation_shortcuts(self, bindings):', SRC)
        self.assertIn('def _update_navigation_shortcuts(self):',SRC)
        self.assertIn('self.canvas_scroll.set_navigation_shortcuts(bindings)',SRC)
        self.assertIn('self._navigation_pressed.get(event.key())',SRC)
        self.assertIn('actual == required',SRC)
        self.assertIn('shortcut.setEnabled(False)', SRC)
        self.assertIn('self._update_navigation_shortcuts()\n            dialog.accept()',SRC)

    def test_preferences_detect_conflicts_and_reset_defaults(self):
        self.assertIn("find_shortcut_conflicts(sequences)",SRC)
        self.assertIn('editors[name].setKeySequence(QKeySequence(default))', SRC)
        self.assertIn("'ctrl+n','ctrl+o','ctrl+s'", SRC)
        self.assertNotIn("Space is reserved for canvas panning", SRC)

    def test_versions_and_file_format(self):
        self.assertIn('APP_VERSION = "0.38.1"',SRC)
        self.assertIn('PROJECT_VERSION = 6',SRC)
        self.assertIn("VERSION = '0.38.1'",(ROOT/'tools/package_release.py').read_text())

try:
    from PySide6.QtCore import Qt, QEvent
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    from main import PannableScrollArea
    HAS_QT=True
except ImportError:
    HAS_QT=False

@unittest.skipUnless(HAS_QT,'PySide6 not installed')
class NavigationKeyQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])

    def test_custom_rotate_key_and_modified_reset_are_distinct(self):
        area=PannableScrollArea()
        area.set_navigation_shortcuts({
            'rotate':(Qt.Key.Key_F,Qt.KeyboardModifier.NoModifier),
            'zoom':(Qt.Key.Key_Z,Qt.KeyboardModifier.NoModifier),
            'pan':(Qt.Key.Key_Space,Qt.KeyboardModifier.NoModifier),
        })
        ev=lambda key,mods: QKeyEvent(QEvent.Type.KeyPress,key,mods)
        self.assertEqual(area._navigation_press_mode(ev(Qt.Key.Key_F,Qt.KeyboardModifier.NoModifier)),'rotate')
        self.assertIsNone(area._navigation_press_mode(ev(Qt.Key.Key_R,Qt.KeyboardModifier.NoModifier)))
        self.assertIsNone(area._navigation_press_mode(ev(Qt.Key.Key_F,Qt.KeyboardModifier.ControlModifier)))
        self.assertIsNone(area._navigation_press_mode(ev(Qt.Key.Key_R,Qt.KeyboardModifier.ControlModifier)))

    def test_modifier_chord_for_pan(self):
        area=PannableScrollArea()
        area.set_navigation_shortcuts({'pan':(Qt.Key.Key_Space,Qt.KeyboardModifier.ShiftModifier)})
        ev=lambda mods: QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Space,mods)
        self.assertEqual(area._navigation_press_mode(ev(Qt.KeyboardModifier.ShiftModifier)),'pan')
        self.assertIsNone(area._navigation_press_mode(ev(Qt.KeyboardModifier.NoModifier)))

if __name__=='__main__':unittest.main()
