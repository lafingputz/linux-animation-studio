"""No-Qt unit tests for the bulk-frame undo transaction, including motion keys."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'main.py').read_text(encoding='utf-8')
tree = ast.parse(source)
canvas_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Canvas')
methods = [n for n in canvas_cls.body if isinstance(n, ast.FunctionDef)
           and n.name in ('add_multiple_blank_frames', '_apply')]
namespace = {}
exec(compile(ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[])), '<frame-test>', 'exec'), namespace)

class Event:
    def emit(self, *args):
        pass

class Obj:
    def __init__(self):
        self.id = 'motion'
        self.keys = {0: (0,0,100,0), 2: (7,0,100,0)}

class FakeCanvas:
    add_multiple_blank_frames = namespace['add_multiple_blank_frames']
    _apply = namespace['_apply']
    def __init__(self):
        self.frames = [['first'], ['second'], ['third']]
        self.frame_index = 0
        self.layers = self.frames[0]
        self.active_id = 'layer'
        self.motion_objects = [Obj()]
        self.playing = False
        self.drawing = False
        self.drag_origin = None
        self.transform_session = None
        self.motion_changed = Event()
        self.playhead_changed = Event()
        self.document_changed = Event()
        self.frames_changed = Event()
        self.command = None
    def _copy_layers(self, source, duplicate=False):
        return ['blank']
    def _motion_key_snapshot(self):
        return {obj.id: dict(obj.keys) for obj in self.motion_objects}
    def _push(self, cmd):
        self.command = cmd
    def update(self):
        pass
    def _mark_dirty(self):
        pass

class MultiFrameTests(unittest.TestCase):
    def test_insertion_undo_redo_shifts_motion_keys_once(self):
        c = FakeCanvas()
        self.assertTrue(c.add_multiple_blank_frames(2))
        self.assertEqual(c.frames, [['first'], ['blank'], ['blank'], ['second'], ['third']])
        self.assertEqual(sorted(c.motion_objects[0].keys), [0,4])
        self.assertEqual(c.command['type'], 'frame_add_multi')
        c._apply(c.command, False)
        self.assertEqual(c.frames, [['first'], ['second'], ['third']])
        self.assertEqual(sorted(c.motion_objects[0].keys), [0,2])
        c._apply(c.command, True)
        self.assertEqual(sorted(c.motion_objects[0].keys), [0,4])
    def test_append_keeps_previous_motion_keys(self):
        c = FakeCanvas()
        self.assertTrue(c.add_multiple_blank_frames(3, at_end=True))
        self.assertEqual(c.frames[-3:], [['blank']] * 3)
        self.assertEqual(sorted(c.motion_objects[0].keys), [0,2])
    def test_rejects_over_limit_and_during_playback(self):
        c = FakeCanvas()
        self.assertFalse(c.add_multiple_blank_frames(118))
        self.assertFalse(c.add_multiple_blank_frames(0))
        c.playing = True
        self.assertFalse(c.add_multiple_blank_frames(1))
        self.assertEqual(len(c.frames), 3)

if __name__ == '__main__':
    unittest.main()
