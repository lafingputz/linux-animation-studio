"""Runs without Qt to validate the release's packaging helper and source metadata."""
import ast
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ReleaseStructureTests(unittest.TestCase):
    def test_source_syntax_and_version(self):
        source = (ROOT / 'main.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('APP_VERSION = "0.28.0"', source)
        self.assertIn('PROJECT_VERSION = 6', source)
        self.assertNotIn('palette(mid)', source)

    def test_build_dry_run(self):
        result = subprocess.run([sys.executable, str(ROOT/'tools'/'build.py'), '--dry-run'],
                                cwd=ROOT, check=True, capture_output=True, text=True)
        self.assertIn('PyInstaller', result.stdout)
        self.assertIn('--onedir', result.stdout)

if __name__ == '__main__':
    unittest.main()
