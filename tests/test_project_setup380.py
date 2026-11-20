"""v0.40.0 new project conversions, presets, and preferences hooks."""
from pathlib import Path
import unittest
from project_setup import PROJECT_PRESETS, preset_dimensions, pixels_to_unit, unit_to_pixels, validate_project_dimensions

ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/'main.py').read_text(encoding='utf-8')

class ProjectSetupTests(unittest.TestCase):
    def test_default_and_video_presets(self):
        self.assertEqual(preset_dimensions('default'),(1200,800))
        self.assertEqual(preset_dimensions('square'),(2048,2048))
        self.assertEqual(preset_dimensions('1080'),(1920,1080))
        self.assertEqual(preset_dimensions('4k'),(4096,1714))
        self.assertEqual(preset_dimensions('uhd'),(3840,2160))

    def test_physical_presets(self):
        self.assertEqual(preset_dimensions('a4',300),(2480,3508))
        self.assertEqual(preset_dimensions('photo',300),(1800,1200))
        self.assertEqual(preset_dimensions('letter',300),(3300,2550))
        self.assertEqual(preset_dimensions('photo',72),(432,288))

    def test_units_roundtrip(self):
        for v in (1,300,1200,4096):
            for unit in ('px','in','mm'):
                self.assertLessEqual(abs(unit_to_pixels(pixels_to_unit(v,unit,300),unit,300)-v),1)

    def test_validation_and_unknown(self):
        for args in ((0,100),(100,0),(16385,50)):
            with self.assertRaises(ValueError):validate_project_dimensions(*args)
        with self.assertRaises(ValueError):preset_dimensions('custom')
        with self.assertRaises(ValueError):unit_to_pixels(2,'bogus',300)

    def test_runtime_wiring(self):
        for token in ('class NewProjectDialog(QDialog):','def show_preferences(self):',
                      "('a4', 'A4 Portrait", "self.canvas.fps = fps", "self._apply_appearance()",
                      "'appearance/theme'", "'appearance/accent'",'PROJECT_VERSION = 6',
                      'APP_VERSION = "0.40.0"'):
            with self.subTest(token=token):self.assertIn(token, SRC if token!="('a4', 'A4 Portrait" else (ROOT/'project_setup.py').read_text(encoding='utf-8'))

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QSettings
    from main import NewProjectDialog, make_application_palette
    HAS_QT=True
except ImportError:
    HAS_QT=False

@unittest.skipUnless(HAS_QT,'PySide6 unavailable')
class ProjectDialogQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_create_default_and_preset(self):
        settings=QSettings(QSettings.Format.IniFormat,QSettings.Scope.UserScope,'LASTest380','dialog')
        settings.clear()
        dialog=NewProjectDialog(settings)
        self.assertEqual(dialog.project_values(),(1200,800,12))
        dialog.preset.setCurrentIndex(dialog.preset.findData('1080'))
        self.assertEqual(dialog.project_values(),(1920,1080,12))
        dialog.unit.setCurrentIndex(dialog.unit.findData('mm'))
        self.assertEqual(dialog.project_values(),(1920,1080,12))
        dialog.fps.setValue(24)
        self.assertEqual(dialog.project_values(),(1920,1080,24))
        dialog.save_defaults()
        other=NewProjectDialog(settings)
        self.assertEqual(other.project_values(),(1920,1080,24))

if __name__=='__main__':unittest.main()
