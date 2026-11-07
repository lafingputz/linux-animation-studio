"""Static docking/menu checks runnable without Qt dependencies."""
from pathlib import Path
import ast
import unittest

MAIN = Path(__file__).resolve().parents[1] / 'main.py'
class DockStructureTests(unittest.TestCase):
    def test_dock_names_native_features_and_layout_keys(self):
        src = MAIN.read_text(encoding='utf-8')
        ast.parse(src)
        self.assertIn('QDockWidget(', src)
        self.assertIn("('timeline', Qt.DockWidgetArea.BottomDockWidgetArea, self.timeline_container)", src)
        self.assertIn('DockWidgetFloatable', src)
        self.assertIn("self._workspace_key('dock_state')", src)
        self.assertIn('def _recover_offscreen_docks', src)
    def test_waveform_outside_tabs_and_animation_menu(self):
        src = MAIN.read_text(encoding='utf-8')
        self.assertIn('timeline.addWidget(self.frame_list)\n        timeline.addWidget(self.audio_wave)', src)
        self.assertIn("menu = self.menuBar().addMenu('&Animation')", src)
        self.assertIn("'Add Multiple Frames', 'Alt+Shift+N'", src)

if __name__ == '__main__':
    unittest.main()
