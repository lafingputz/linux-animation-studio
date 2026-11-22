"""Regression coverage for v0.41 pressure controls and numeric reset menus."""
import ast
import unittest
from pathlib import Path
from unittest.mock import Mock

SOURCE = (Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)


class PressureControlTests(unittest.TestCase):
    def test_builtin_pressure_size(self):
        canvas = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'Canvas')
        stroke = next(n for n in canvas.body if isinstance(n, ast.FunctionDef) and n.name == 'stroke')
        assignments = [n for n in stroke.body if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id in ('strength', 'width') for t in n.targets)]
        self.assertEqual(len(assignments), 2)
        code = compile(ast.Module(body=assignments, type_ignores=[]), '<pressure>', 'exec')
        c = Mock()
        c.size = 40
        c.tool = 'brush'
        c.brush_preset = 'Round'
        for strength, expected in [(0, 40), (50, 31.5), (100, 23)]:
            c.brush_settings = {'Round': {'pressure_size': strength}}
            ns = {'self': c, 'pressure': .5, 'tablet': True}
            exec(code, ns)
            self.assertAlmostEqual(ns['width'], expected)
            ns['tablet'] = False
            exec(code, ns)
            self.assertEqual(ns['width'], 40)

    def test_builtin_pressure_opacity_and_setting_wiring(self):
        self.assertIn("self.brush_settings[preset].get('pressure_opacity', 0)", SOURCE)
        self.assertIn("elif key in ('pressure_size', 'pressure_opacity'):", SOURCE)
        self.assertIn("self.canvas.brush_settings[self.canvas.brush_preset][key] = value", SOURCE)
        self.assertIn("self._sync_builtin_pressure_controls()", SOURCE)

    def test_timeline_and_audio_reset_defaults(self):
        for pair in ('(self.fps_input, 12)', '(self.onion_spin, 35)',
                     '(self.onion_previous_input, 1)', '(self.onion_next_input, 1)',
                     '(self.audio_volume, 100)', '(self.audio_gain, 100)'):
            self.assertIn(pair, SOURCE)
        self.assertIn('editor.customContextMenuRequested.connect(', SOURCE)
        self.assertIn('slider.customContextMenuRequested.connect(', SOURCE)


if __name__ == '__main__':
    unittest.main()
