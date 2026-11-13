"""Static guards for menu event-loop stability; device validation still required."""
from pathlib import Path
import unittest

SRC = (Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8')

class TabletMenu352Tests(unittest.TestCase):
    def test_nonblocking_context_menu(self):
        block = SRC.split('    def _canvas_context_menu(self, global_pos):', 1)[1].split('    def _timeline_context_menu(',1)[0]
        self.assertIn('menu.popup(global_pos)', block)
        self.assertNotIn('menu.exec(global_pos)', block)
        self.assertIn('active_menu.isVisible()', block)
        self.assertIn('menu.aboutToHide.connect(clear_active_menu)', block)

    def test_single_secondary_tablet_gesture(self):
        block = SRC.split('    def tabletEvent(self, event):',1)[1].split('    def mouseDoubleClickEvent(',1)[0]
        self.assertIn('self._secondary_tablet_down', block)
        self.assertIn('QTimer.singleShot(0,', block)

    def test_no_synthetic_duplicate(self):
        block = SRC.split('    def contextMenuEvent(self, event):',1)[1].split('    def mousePressEvent(',1)[0]
        self.assertIn('not self._secondary_tablet_down', block)

if __name__ == '__main__':
    unittest.main()
