"""Regression coverage for macOS native menu roles and bundle metadata."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class MacPreferencesRoutingTests(unittest.TestCase):
    def test_explicit_native_menu_roles(self):
        code = (ROOT / "main.py").read_text()
        self.assertIn("preferences_action.setMenuRole(QAction.MenuRole.PreferencesRole)", code)
        self.assertIn("feedback_action.setMenuRole(QAction.MenuRole.NoRole)", code)
        self.assertIn("about_action.setMenuRole(QAction.MenuRole.AboutRole)", code)
        self.assertIn("app.setApplicationDisplayName('Linux Animation Studio')", code)

    def test_packaged_application_display_name(self):
        code = (ROOT / "tools" / "build.py").read_text()
        self.assertIn("info['CFBundleName'] = 'Linux Animation Studio'", code)
        self.assertIn("info['CFBundleDisplayName'] = 'Linux Animation Studio'", code)

    def test_macos_ignored_files(self):
        text = (ROOT / ".gitignore").read_text()
        self.assertIn(".DS_Store", text)

if __name__ == "__main__":
    unittest.main()
