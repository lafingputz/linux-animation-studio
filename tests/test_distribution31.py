"""Dependency-free v0.31 tests (no GUI or PyInstaller installation needed)."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from package_release import package_plan, inno_script, APP, VERSION


class DistributionTests(unittest.TestCase):
    def test_version_and_source(self):
        main = (ROOT / 'main.py').read_text(encoding='utf-8')
        self.assertIn('APP_VERSION = "0.37.1"', main)
        self.assertIn('PROJECT_VERSION = 6', main)
        self.assertIn('self._refresh_recent_projects()', main)
        self.assertIn('self._remember_project(path)', main)
        self.assertIn('def _open_path(self, path):', main)
        self.assertIn('if not Path(path).is_file():', main)

    def test_platform_packages(self):
        with tempfile.TemporaryDirectory() as td:
            for platform, typ, ext in [('win32','inno','.exe'),('darwin','dmg','.dmg'),('linux','tar','.tar.gz')]:
                kind,bundle,binary,target = package_plan(td, platform)
                self.assertEqual(kind, typ)
                self.assertTrue(str(target).endswith(ext))
                self.assertTrue(APP in str(binary))

    def test_windows_inno_script(self):
        with tempfile.TemporaryDirectory() as td:
            script = inno_script(Path(td)/APP,Path(td)/'releases'/'test.exe')
            self.assertIn('[Setup]',script)
            self.assertIn('PrivilegesRequired=lowest',script)
            self.assertIn('[Icons]',script)
            self.assertIn('recursesubdirs',script)
            self.assertIn('AppVersion=0.37.1',script)

    def test_icons_exist(self):
        for ext in ('png','ico','icns'):
            icon = ROOT / 'assets' / ('las.'+ext)
            self.assertGreater(icon.stat().st_size, 500)


if __name__ == '__main__':
    unittest.main()
