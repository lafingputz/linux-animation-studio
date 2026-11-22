"""Qt-independent regression checks for the v0.40.0 contextual Tools dock."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'main.py').read_text(encoding='utf-8')

class ContextualToolsSourceTests(unittest.TestCase):
    def test_existing_widgets_are_grouped_without_recreation_on_switch(self):
        window = SOURCE[SOURCE.index('class MainWindow(QMainWindow):'):]
        section = window[window.index("self.tool_sections = {}"):window.index('settings_scroll = QScrollArea()')]
        self.assertIn("section_layouts['fill'].addWidget(self._slider_row(self.fill_tolerance_input))", section)
        slider_factory = window[window.index('def _slider_row('):window.index('def _populate_audio_menu(')]
        self.assertIn('layout.addWidget(spin)', slider_factory)
        self.assertIn('slider.valueChanged.connect(spin.setValue)', slider_factory)
        self.assertIn('spin.valueChanged.connect(slider.setValue)', slider_factory)
        self.assertIn("section_layouts['brush'].addWidget(self.brush_select)",section)
        self.assertIn("section_layouts['select'].addWidget(self.selection_mode_picker)",section)
        self.assertIn("section_layouts['shared'].addLayout(size_row)",section)
        update = window[window.index('def _update_tool_context('):window.index('def set_tool(')]
        self.assertIn('widget.setVisible(section in visible)', update)
        self.assertNotIn('QSpinBox(', update)
        self.assertNotIn('QComboBox(', update)

    def test_active_tool_changes_context(self):
        source = SOURCE[SOURCE.index('def set_tool(self, tool):'):SOURCE.index('def adjust_brush(self, offset):')]
        self.assertIn('self._update_tool_context()', source)
        self.assertIn("'brush': 'Brush Settings'", SOURCE)
        self.assertIn("'fill': 'Paint Bucket Settings'", SOURCE)

    def test_per_setting_reset_menu(self):
        self.assertIn("menu.addAction('Reset to Default Value')", SOURCE)
        self.assertIn('self._install_tool_setting_resets()', SOURCE)
        self.assertIn('self._default_tool_size()', SOURCE)
        self.assertIn('self.fill_expansion_input: 2', SOURCE)
        self.assertIn("defaults[widget] = 100 if name == 'pressure_size' else 0",SOURCE)

    def test_no_document_format_bump(self):
        self.assertIn('APP_VERSION = "0.40.0"',SOURCE)
        self.assertIn('PROJECT_VERSION = 6',SOURCE)
        self.assertIn("VERSION = '0.40.0'",(ROOT/'tools/package_release.py').read_text(encoding='utf-8'))

if __name__ == '__main__': unittest.main()
