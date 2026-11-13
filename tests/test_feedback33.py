"""Beta feedback tests; run without PySide6 or network access."""
import ast
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from feedback_support import feedback_url, normalize_repository, read_packaged_repository, support_diagnostics


class FeedbackTests(unittest.TestCase):
    def test_valid_repository_and_direct_issue_forms(self):
        self.assertEqual(normalize_repository('https://github.com/Artist/LAS.git'), 'Artist/LAS')
        self.assertEqual(feedback_url('Artist/LAS', 'bug'),
                         'https://github.com/Artist/LAS/issues/new?template=01_bug_report.yml')
        self.assertEqual(feedback_url('Artist/LAS', 'feature'),
                         'https://github.com/Artist/LAS/issues/new?template=02_feature_request.yml')

    def test_rejects_untrusted_repository_sources(self):
        for target in ['', 'http://github.com/artist/las',
                       'https://evil.example.com/artist/las',
                       'artist/las/issues', 'owner/repo?x=y', 'owner/../repo',
                       'owner/repo#evil', 'owner/repo/extra']:
            with self.subTest(target=target):
                self.assertEqual(normalize_repository(target), '')
                self.assertEqual(feedback_url(target, 'bug'), '')
        self.assertEqual(feedback_url('artist/las', 'anything'), '')

    def test_repo_configuration_read(self):
        with tempfile.TemporaryDirectory() as directory:
            assets = Path(directory) / 'assets'
            assets.mkdir()
            config = assets / 'feedback.json'
            config.write_text('{"repository": "test-user/test-las"}', encoding='utf-8')
            self.assertEqual(read_packaged_repository(directory), 'test-user/test-las')
            config.write_text('{"repository": "https://other-site.example/owner/repo"}', encoding='utf-8')
            self.assertEqual(read_packaged_repository(directory), '')

    def test_diagnostics_exclude_private_information(self):
        text = support_diagnostics('0.33.0', '6.7', '6.7', packaged=True,
                                   os_name='Linux', architecture='x86_64')
        for field in ['LAS version: 0.33.0', 'Installation: packaged', 'Qt: 6.7', 'x86_64']:
            self.assertIn(field, text)
        for field in ['home directory', 'IP address', 'username', 'project file']:
            self.assertNotIn(field, text.lower())

    def test_help_menu_and_local_copy_controls(self):
        main = (ROOT / 'main.py').read_text(encoding='utf-8')
        ast.parse(main)
        for element in ['Report a Bug…', 'Request a Feature…', 'Copy System Information…',
                        'Configure Feedback Repository…', 'QDesktopServices.openUrl(QUrl(url))',
                        'QApplication.clipboard().setText(diagnostics)']:
            self.assertIn(element, main)
        self.assertIn('APP_VERSION = "0.35.1"', main)
        self.assertIn('PROJECT_VERSION = 6', main)

    def test_official_repository_is_packaged_by_default(self):
        self.assertEqual(read_packaged_repository(ROOT), 'lafingputz/linux-animation-studio')
        self.assertEqual(feedback_url(read_packaged_repository(ROOT), 'bug'),
                         'https://github.com/lafingputz/linux-animation-studio/issues/new?template=01_bug_report.yml')

    def test_github_forms_present(self):
        base = ROOT / '.github' / 'ISSUE_TEMPLATE'
        for name in ('01_bug_report.yml', '02_feature_request.yml', 'config.yml'):
            self.assertTrue((base / name).is_file())
        bug = (base / '01_bug_report.yml').read_text(encoding='utf-8')
        feature = (base / '02_feature_request.yml').read_text(encoding='utf-8')
        for expected in ['LAS version', 'Operating system', 'What happened?', 'How can we reproduce it?', 'System information']:
            self.assertIn(expected, bug)
        for expected in ['What problem would this solve?', 'What would you like LAS to do?']:
            self.assertIn(expected, feature)
        self.assertIn('blank_issues_enabled: false',
                      (base / 'config.yml').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
