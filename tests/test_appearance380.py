import unittest
from appearance_support import resolve_system_theme


class SystemThemeTests(unittest.TestCase):
    def test_windows_apps_dark_wins_over_qt_light(self):
        self.assertEqual(resolve_system_theme('win32', windows_light=False, qt_scheme=1), 'Dark')

    def test_windows_apps_light_wins_over_qt_dark(self):
        self.assertEqual(resolve_system_theme('win32', windows_light=True, qt_scheme=2), 'Light')

    def test_unknown_windows_uses_qt(self):
        self.assertEqual(resolve_system_theme('win32', windows_light=None, qt_scheme=2), 'Dark')

    def test_qt_dark_linux_mac(self):
        for platform in ('linux', 'darwin'):
            self.assertEqual(resolve_system_theme(platform, qt_scheme=2), 'Dark')

    def test_qt_light(self):
        self.assertEqual(resolve_system_theme('darwin', qt_scheme=1), 'Light')

    def test_unknown_fallback(self):
        self.assertEqual(resolve_system_theme('linux', qt_scheme=0, fallback_dark=True), 'Dark')
        self.assertEqual(resolve_system_theme('linux', qt_scheme=0, fallback_dark=False), 'Light')


if __name__ == '__main__':
    unittest.main()
