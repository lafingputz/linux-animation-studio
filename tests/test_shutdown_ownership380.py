"""Static regression checks for modal dialog and Qt teardown lifecycle."""
from pathlib import Path
import ast
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ShutdownOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(ROOT/'main.py').read_text(encoding='utf-8')
        cls.tree=ast.parse(cls.source)

    def test_preferences_dialog_deleted_before_theme_reapply(self):
        cls=next(x for x in self.tree.body if isinstance(x,ast.ClassDef) and x.name=='MainWindow')
        method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='show_preferences')
        body=ast.get_source_segment(self.source,method)
        self.assertIn('dialog.deleteLater()',body)
        self.assertIn('QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)',body)
        self.assertLess(body.index('dialog.deleteLater()'),body.index('self._apply_appearance()'))

    def test_main_window_destroyed_before_interpreter_exit(self):
        startup=self.source.split("if __name__ == '__main__':",1)[1]
        self.assertLess(startup.index('exit_code = app.exec()'),startup.index('window.deleteLater()'))
        self.assertLess(startup.index('window.deleteLater()'),startup.index('sys.exit(exit_code)'))

    def test_theme_and_project_preserved(self):
        self.assertIn("app.setStyle('Fusion')",self.source)
        self.assertIn('PROJECT_VERSION = 6',self.source)
        self.assertIn('QAction.MenuRole.PreferencesRole',self.source)

if __name__=='__main__': unittest.main()
