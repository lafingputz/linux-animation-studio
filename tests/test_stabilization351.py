"""v0.35.1 non-GUI source regression checks; interactive tablet testing still required."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / 'main.py').read_text(encoding='utf-8')


class Stabilization351Tests(unittest.TestCase):
    def test_version_and_format(self):
        self.assertIn('APP_VERSION = "0.35.2"', SRC)
        self.assertIn('PROJECT_VERSION = 6', SRC)

    def test_builtin_selection_clears_custom_state(self):
        block = SRC.split('    def change_brush_preset(self, name):', 1)[1].split('    def change_brush_opacity(', 1)[0]
        self.assertIn('self.canvas.active_custom_brush = None', block)
        self.assertIn('self.canvas._stamp_cache.clear()', block)
        quick = SRC.split('    def _quick_brush(self, preset):', 1)[1].split('    def _quick_eraser(', 1)[0]
        self.assertIn('self.change_brush_preset(preset)', quick)

    def test_eye_interaction_consumes_release_and_move(self):
        block = SRC.split('class LayerEyeList(QListWidget):', 1)[1].split('def layer_eye_icon(', 1)[0]
        self.assertIn('self._eye_pressed = True', block)
        self.assertIn('def mouseReleaseEvent(', block)
        self.assertIn('def mouseMoveEvent(', block)
        self.assertIn('self._eye_pressed = False', block)

    def test_right_button_not_treated_as_nib_press(self):
        block = SRC.split('    def tabletEvent(self, event):', 1)[1].split('    def mouseDoubleClickEvent(', 1)[0]
        self.assertIn('is_secondary', block)
        self.assertIn('event.button() != Qt.MouseButton.LeftButton', block)
        self.assertIn('self.canvas_context_requested.emit(', block)

    def test_layer_delete_confirmation_is_undo_accurate(self):
        block = SRC.split('    def _delete_layer_confirmed(self):', 1)[1].split('    def _layer_context_menu(', 1)[0]
        self.assertIn('You can undo this operation.', block)


if __name__ == '__main__':
    unittest.main()
