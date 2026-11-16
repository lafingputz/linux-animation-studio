"""v0.39.0 shortcut collision detection and GUI wiring regression checks."""
import unittest
from pathlib import Path
from shortcut_conflicts import find_shortcut_conflicts

ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/'main.py').read_text(encoding='utf8')

class ShortcutConflictTests(unittest.TestCase):
    def test_both_offending_commands_flagged(self):
        found=find_shortcut_conflicts({'Rotate':'R','Zoom':'R','Pan':'Space'})
        self.assertEqual(found, {'Zoom':['Rotate'],'Rotate':['Zoom']})
    def test_three_way_collision(self):
        found=find_shortcut_conflicts({'Rotate':'R','Zoom':'R','Pan':'r'})
        self.assertEqual(found['Rotate'],['Zoom','Pan'])
        self.assertEqual(found['Zoom'],['Rotate'])
        self.assertEqual(found['Pan'],['Rotate'])
    def test_ignores_empty_and_handles_case(self):
        self.assertEqual(find_shortcut_conflicts({'A':'','B':' ','C':'Ctrl+R','D':'ctrl+r'}),
                         {'D':['C'],'C':['D']})
    def test_no_conflicts_when_unique(self):
        self.assertEqual(find_shortcut_conflicts({'R':'R','Z':'Z','Pan':'Space'}), {})
    def test_live_gui_feedback_and_focus(self):
        for fragment in ('edit.keySequenceChanged.connect', 'edit.setStyleSheet(',
                         'labels[name].setStyleSheet(', 'form_scroll.ensureWidgetVisible(editors[first])',
                         'editors[first].setFocus()', 'conflicts = update_conflicts()',
                         "dialog.accept()"):
            with self.subTest(fragment=fragment): self.assertIn(fragment,SRC)
    def test_version(self):
        self.assertIn('APP_VERSION = "0.39.0"',SRC)
        self.assertIn("VERSION = '0.39.0'",(ROOT/'tools/package_release.py').read_text(encoding='utf-8'))

if __name__=='__main__': unittest.main()
