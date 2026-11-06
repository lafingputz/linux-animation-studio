"""Check expected native-build file layouts without PyInstaller installed."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_build import build_paths, validate_build


class NativeBuildLayoutTests(unittest.TestCase):
    def test_platform_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(build_paths(tmp, 'win32')[1].name, 'LinuxAnimationStudio.exe')
            self.assertEqual(build_paths(tmp, 'linux')[1].name, 'LinuxAnimationStudio')
            self.assertEqual(build_paths(tmp, 'darwin')[1].name, 'LinuxAnimationStudio')
            self.assertIn('.app', str(build_paths(tmp, 'darwin')[0]))

    def test_missing_build_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(validate_build(tmp, 'linux')[2])

    def test_detects_valid_windows_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, binary = build_paths(tmp, 'win32')
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'test')
            self.assertEqual(validate_build(tmp, 'win32')[2], [])


if __name__ == '__main__':
    unittest.main()
