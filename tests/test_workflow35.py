"""Regression coverage for v0.35 layer controls and context menus."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class WorkflowSourceTests(unittest.TestCase):
    def test_version_and_requested_actions(self):
        source = (ROOT / 'main.py').read_text(encoding='utf-8')
        self.assertIn('APP_VERSION = "0.37.1"', source)
        for target in ('class LayerEyeList(', 'def layer_eye_icon(',
                       'def _toggle_layer_visibility_by_id(',
                       'def _layer_context_menu(', 'def _canvas_context_menu(',
                       'def _timeline_context_menu(', 'Multi-frame Edit',
                       'Link Selected Frames From Current Cel', 'Unlink Selected Frames'):
            with self.subTest(target=target):
                self.assertIn(target, source)

    def test_do_not_change_project_format(self):
        source = (ROOT / 'main.py').read_text(encoding='utf-8')
        self.assertIn('PROJECT_VERSION = 6', source)

    def test_release_artifacts_ignored(self):
        ignore = (ROOT / '.gitignore').read_text(encoding='utf-8')
        self.assertIn('/releases/', ignore)


try:
    from PySide6.QtCore import Qt, QPoint
    from PySide6.QtWidgets import QApplication
    from main import MainWindow
    HAS_QT = True
except ImportError:
    HAS_QT = False


@unittest.skipUnless(HAS_QT, 'PySide6 is not installed')
class WorkflowQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.project_active = True
        self.window.refresh_layers()

    def tearDown(self):
        # GUI cleanup must not open an unsaved-changes confirmation dialog.
        self.window._confirm_discard = lambda: True
        self.window.close()

    def test_layer_eye_does_not_select_other_layer(self):
        canvas = self.window.canvas
        canvas.new_layer()
        initial = canvas.active_id
        other = next(l.id for l in canvas.layers if l.id != initial)
        previous = canvas.layer_by_id(other).visible
        self.window._toggle_layer_visibility_by_id(other)
        self.assertEqual(canvas.active_id, initial)
        self.assertNotEqual(canvas.layer_by_id(other).visible, previous)
        canvas.undo()
        self.assertEqual(canvas.active_id, initial)
        self.assertEqual(canvas.layer_by_id(other).visible, previous)

    def test_quick_toggle_tracks_multiframe_state(self):
        self.window.multi_edit_quick_toggle.setChecked(True)
        self.assertTrue(self.window.multi_edit_checkbox.isChecked())
        self.assertTrue(self.window.canvas.multi_edit_enabled)
        self.window.multi_edit_checkbox.setChecked(False)
        self.assertFalse(self.window.multi_edit_quick_toggle.isChecked())
        self.assertFalse(self.window.canvas.multi_edit_enabled)
