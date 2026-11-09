"""Runs without Qt to validate the release's packaging helper and source metadata."""
import ast
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ReleaseStructureTests(unittest.TestCase):
    def test_source_syntax_and_version(self):
        source = (ROOT / 'main.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('APP_VERSION = "0.34.0"', source)
        self.assertIn('PROJECT_VERSION = 6', source)
        self.assertNotIn('palette(mid)', source)

    def test_color_button_stylesheet_has_one_matching_rule_brace(self):
        """Catch literal doubled braces in a string following an f-string.

        This caused the color QPushButton stylesheet to parse incorrectly
        whenever the UI refreshed at startup or after project actions.
        """
        source = (ROOT / 'main.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        main_window = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MainWindow')
        method = next(n for n in main_window.body if isinstance(n, ast.FunctionDef) and n.name == 'update_color_swatch')
        # Execute just this method with fake widgets to test the stylesheet
        # that actually results from the adjacent f-string/plain-string literals.
        isolated = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
        namespace = {}
        exec(compile(isolated, str(ROOT / 'main.py'), 'exec'), namespace)

        class FakeColor:
            def name(self):
                return '#123456'

        class FakeButton:
            def setText(self, text):
                self.text = text
            def setToolTip(self, tooltip):
                self.tooltip = tooltip
            def setStyleSheet(self, stylesheet):
                self.stylesheet = stylesheet

        class FakeCanvas:
            color = FakeColor()

        class FakeWindow:
            canvas = FakeCanvas()
            color_button = FakeButton()

        window = FakeWindow()
        namespace['update_color_swatch'](window)
        css = window.color_button.stylesheet
        self.assertEqual(css.count('{'), 1, css)
        self.assertEqual(css.count('}'), 1, css)
        self.assertIn('color: #123456;', css)
        self.assertTrue(css.rstrip().endswith('}'), css)

    def test_build_dry_run(self):
        result = subprocess.run([sys.executable, str(ROOT/'tools'/'build.py'), '--dry-run'],
                                cwd=ROOT, check=True, capture_output=True, text=True)
        self.assertIn('PyInstaller', result.stdout)
        self.assertIn('--onedir', result.stdout)

if __name__ == '__main__':
    unittest.main()
