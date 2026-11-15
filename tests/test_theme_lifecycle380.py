"""Regression tests for the macOS/Linux native theme shutdown crash."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ThemeLifecycleTests(unittest.TestCase):
    def test_fusion_installed_only_once_before_window(self):
        source = (ROOT / 'main.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == 'setStyle']
        self.assertEqual(len(calls), 1, 'Qt QStyle must never be replaced during theme switching')
        startup = source[source.index("if __name__ == '__main__':"):]
        self.assertLess(startup.index("app.setStyle('Fusion')"), startup.index('window = MainWindow()'))

    def test_idempotent_theme_changes(self):
        source = (ROOT / 'main.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MainWindow')
        method = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == '_apply_appearance')
        attrs = [n.attr for n in ast.walk(method) if isinstance(n, ast.Attribute)]
        self.assertNotIn('setStyle', attrs)
        self.assertIn('_las_applied_appearance', attrs)
        self.assertIn('setPalette', attrs)
        self.assertIn('setStyleSheet', attrs)

    def test_project_format_and_macos_menu_roles_preserved(self):
        source = (ROOT / 'main.py').read_text(encoding='utf-8')
        self.assertIn('PROJECT_VERSION = 6', source)
        self.assertIn('preferences_action.setMenuRole(QAction.MenuRole.PreferencesRole)', source)
        self.assertIn('feedback_action.setMenuRole(QAction.MenuRole.NoRole)', source)

if __name__ == '__main__':
    unittest.main()
