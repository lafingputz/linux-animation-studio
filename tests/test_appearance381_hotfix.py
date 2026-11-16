"""Cross-platform source checks for the v0.39.0 visual corrections."""
import unittest
from pathlib import Path

MAIN = (Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8')


class Appearance381CorrectionTests(unittest.TestCase):
    def test_accent_contrast_uses_linear_srgb_luminance(self):
        self.assertIn('def accent_foreground(accent):', MAIN)
        self.assertIn('0.7152 * linear(color.green())', MAIN)
        self.assertIn('contrast_black >= contrast_white', MAIN)
        self.assertIn('QPalette.ColorRole.HighlightedText: accent_foreground(accent)', MAIN)

    def test_selected_list_item_uses_same_readable_foreground(self):
        self.assertIn('QListWidget::item:selected, QListView::item:selected', MAIN)
        self.assertIn('background-color: {accent}; color: {selected};', MAIN)
        self.assertIn('selected=selected_text', MAIN)

    def test_split_buttons_have_room_for_their_arrow(self):
        for button in ('brush_button', 'eraser_button', 'select_button'):
            self.assertIn(f'{button}.setMinimumWidth(55)', MAIN)
        self.assertIn('border: 2px solid transparent;', MAIN)
        self.assertIn('border-color: {accent}', MAIN)

    def test_dock_titles_follow_current_theme(self):
        self.assertIn("dock_title_bg = '#d6dde7' if not dark else '#40546b'", MAIN)
        self.assertIn("dock_title_fg = '#20232b' if not dark else '#f3f7fd'", MAIN)
        self.assertIn('QDockWidget::title {', MAIN)
        self.assertIn('self.setStyleSheet(', MAIN)

    def test_preferences_shortcut_is_customizable_and_native_menu_role_maintained(self):
        self.assertIn("('Preferences', 'Ctrl+,', self.show_preferences)", MAIN)
        self.assertIn('preferences_action.setMenuRole(QAction.MenuRole.PreferencesRole)', MAIN)
        self.assertIn("sequence = str(self.preferences.value('shortcuts/' + name, default))", MAIN)

    def test_theme_still_initializes_fusion_only_once(self):
        self.assertEqual(MAIN.count("app.setStyle('Fusion')"), 1)
        self.assertIn("window.deleteLater()", MAIN)
