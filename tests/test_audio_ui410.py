"""Hardware-independent tests for the v0.41 audio interface."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock

SOURCE = (Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)
WINDOW = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'MainWindow')


def method(name):
    node = next(n for n in WINDOW.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<audio-ui-test>', 'exec'), namespace)
    return namespace[name]


class AudioUITests(unittest.TestCase):
    def test_visual_gain_only_updates_display_and_preferences(self):
        ui = Mock()
        method('_set_waveform_gain')(ui, 250)
        self.assertEqual(ui.audio_wave.display_gain, 250)
        ui.audio_wave.update.assert_called_once_with()
        ui.preferences.setValue.assert_called_once_with('audio/display_gain', 250)
        self.assertEqual(ui.audio_output.mock_calls, [])
        self.assertEqual(ui.audio_player.mock_calls, [])
        self.assertEqual(ui.canvas.mock_calls, [])

    def test_autofit_and_silence(self):
        ui = Mock()
        for peaks, expected in [([.02, .2], 500), ([1.0], 100), ([0, 0], 100), ([], 100)]:
            ui.audio_wave.peaks = peaks
            method('_auto_fit_waveform')(ui)
            ui.audio_gain.setValue.assert_called_with(expected)

    def test_disabled_scrub_does_not_preview(self):
        ui = Mock()
        ui._audio_scrubbing = True
        ui.canvas.playing = False
        ui.canvas.audio_bytes = b'audio'
        ui.audio_scrub_enabled.isChecked.return_value = False
        method('_preview_scrub_audio')(ui)
        ui.audio_player.play.assert_not_called()
        ui.scrub_preview_timer.start.assert_not_called()

    def test_disable_scrub_stops_preview(self):
        ui = Mock()
        method('_set_audible_scrub')(ui, False)
        ui._stop_scrub_preview.assert_called_once_with()
        ui.scrub_preview_timer.stop.assert_called_once_with()

    def test_audio_menu_and_context_share_actions(self):
        self.assertIn("self.menuBar().addMenu('&Audio')", SOURCE)
        self.assertIn('self._populate_audio_menu(menu)', SOURCE)
        self.assertIn('self.audio_wave.customContextMenuRequested.connect(self._audio_context_menu)', SOURCE)
        self.assertNotIn("audio = menu.addMenu('Audio')", SOURCE)


if __name__ == '__main__':
    unittest.main()
