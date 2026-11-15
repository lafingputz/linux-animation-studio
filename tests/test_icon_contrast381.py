"""Regression checks for contrast-aware raster drawing tool icons."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8')


class ToolIconContrastTests(unittest.TestCase):
    def test_checked_icons_use_accent_foreground_and_alpha_mask(self):
        icon_code = SOURCE.split('    def _small_tool_icon(self, tool):', 1)[1].split('    def _refresh_tool_icons(self):', 1)[0]
        self.assertIn('button.isChecked()', icon_code)
        self.assertIn('accent_foreground(accent)', icon_code)
        self.assertIn('CompositionMode_SourceIn', icon_code)
        self.assertIn('icon_painter.fillRect(img.rect()', icon_code)

    def test_appearance_refreshes_icons_when_accent_changes(self):
        method = SOURCE.split('    def _apply_appearance(self):', 1)[1].split('    def show_preferences(self):', 1)[0]
        self.assertIn('self._refresh_tool_icons()', method)
        self.assertLess(method.index('app._las_applied_appearance = appearance_key'), method.index('self._refresh_tool_icons()'))

    def test_existing_split_button_spacing_is_unchanged(self):
        for name in ('brush_button', 'eraser_button', 'select_button'):
            self.assertIn(f'{name}.setMinimumWidth(55)', SOURCE)
        self.assertIn('padding: 0px; margin: 0px;', SOURCE)


if __name__ == '__main__':
    unittest.main()
