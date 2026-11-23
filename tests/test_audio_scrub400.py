"""Regression checks for v0.41.0-rc.1 audible timeline scrubbing.

These source-level checks run without audio hardware. Native manual tests are
still required because QMediaPlayer backends behave differently across OSes.
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "main.py").read_text(encoding="utf-8")


class AudibleScrubTests(unittest.TestCase):
    def test_source_is_syntactically_valid(self):
        ast.parse(SOURCE, filename="main.py")

    def test_audio_waveform_has_gesture_lifecycle(self):
        waveform = SOURCE.split("class AudioWaveform(QWidget):", 1)[1].split(
            "class ExposureFrameList(", 1)[0]
        self.assertIn("self.on_scrub_start()", waveform)
        self.assertIn("self.on_scrub_end()", waveform)
        self.assertIn("self.on_seek(", waveform)
        self.assertIn("self._scrubbing = False", waveform)

    def test_preview_is_bounded_and_respects_controls(self):
        window = SOURCE.split("class MainWindow(QMainWindow):", 1)[1]
        self.assertIn("self.scrub_preview_timer.setSingleShot(True)", window)
        self.assertIn("self.scrub_preview_timer.start(140)", window)
        self.assertIn("now - self._last_scrub_preview < 0.08", window)
        self.assertIn("self.audio_output.isMuted()", window)
        self.assertIn("self.audio_output.volume() <= 0", window)
        end = window.split("def _end_audio_scrub(self):", 1)[1].split(
            "def _preview_scrub_audio(self):", 1)[0]
        self.assertIn("self.scrub_preview_timer.stop()", end)
        self.assertIn("self.audio_player.pause()", end)

    def test_playback_and_import_cleanup(self):
        self.assertIn("self.audio_wave.on_scrub_start = self._begin_audio_scrub", SOURCE)
        self.assertIn("self.audio_wave.on_scrub_end = self._end_audio_scrub", SOURCE)
        self.assertIn("def toggle_playback(self):\n        self._end_audio_scrub()", SOURCE)
        self.assertIn("def _reset_audio(self):\n        self._end_audio_scrub()", SOURCE)
        self.assertIn("def _reload_audio(self):\n        self._end_audio_scrub()", SOURCE)

    def test_project_format_unchanged(self):
        self.assertIn('APP_VERSION = "0.41.0-rc.1"', SOURCE)
        self.assertIn("PROJECT_VERSION = 6", SOURCE)


if __name__ == "__main__":
    unittest.main()
