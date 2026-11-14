"""Regression checks for customizable Reset Canvas Rotation (Ctrl+R/Cmd+R)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / 'main.py').read_text(encoding='utf-8')

class RotationResetShortcutTests(unittest.TestCase):
    def test_default_shortcut_and_customization(self):
        self.assertIn("('Reset Canvas Rotation', 'Ctrl+R', self.reset_canvas_rotation)", SRC)
        self.assertIn("self._shortcut_objects['Reset Canvas Rotation']", SRC)
        self.assertIn('self._update_reset_rotation_shortcut_hint()', SRC)
        self.assertIn("self._reset_rotation_action = viewmenu.addAction", SRC)

    def test_modified_r_does_not_trigger_temporary_rotate(self):
        self.assertIn('has_command_modifier = bool(event.modifiers()', SRC)
        self.assertIn('Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier', SRC)
        self.assertIn("mode in ('rotate', 'zoom') and has_command_modifier", SRC)

    def test_version_and_project_compatibility(self):
        self.assertIn('APP_VERSION = "0.37.1"', SRC)
        self.assertIn('PROJECT_VERSION = 6', SRC)
        self.assertIn("VERSION = '0.37.1'", (ROOT / 'tools/package_release.py').read_text(encoding='utf-8'))

if __name__ == '__main__':
    unittest.main()
