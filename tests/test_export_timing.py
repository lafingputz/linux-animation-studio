"""Non-Qt tests for output FPS mapping, useful on build-only systems."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def export_mapper():
    tree = ast.parse((ROOT / 'main.py').read_text(encoding='utf-8'))
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
              and node.name == 'source_frame_for_export')
    isolated = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    ns = {}
    exec(compile(isolated, 'main.py', 'exec'), ns)
    return ns['source_frame_for_export']


class ExportTimingTests(unittest.TestCase):
    def test_higher_fps_repeats_without_skipping(self):
        mapper = export_mapper()
        self.assertEqual([mapper(i, 12, 24, 3) for i in range(6)],
                         [0, 0, 1, 1, 2, 2])

    def test_lower_fps_samples_source_frames(self):
        mapper = export_mapper()
        self.assertEqual([mapper(i, 24, 12, 6) for i in range(3)],
                         [0, 2, 4])

    def test_uneven_rate_and_end_clamp(self):
        mapper = export_mapper()
        self.assertEqual([mapper(i, 10, 15, 3) for i in range(5)],
                         [0, 0, 1, 2, 2])
        self.assertEqual(mapper(999, 12, 24, 3), 2)

    def test_invalid_settings(self):
        mapper = export_mapper()
        for args in [(-1, 12, 24, 3), (0, 0, 24, 3),
                     (0, 12, 0, 3), (0, 12, 24, 0)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                mapper(*args)


if __name__ == '__main__':
    unittest.main()
