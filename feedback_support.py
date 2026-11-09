"""Privacy-conscious LAS feedback destinations and support information.

This module intentionally has no Qt dependency so it can be unit-tested on
Windows, Linux, and macOS even before PySide6 is installed.
"""
import json
import platform
import re
import sys
from pathlib import Path

_GITHUB_REPOSITORY = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}$')


def normalize_repository(value):
    """Accept owner/repo or a canonical github.com repo URL, never a foreign host."""
    if not isinstance(value, str):
        return ''
    repo = value.strip().rstrip('/')
    if repo.startswith('https://github.com/'):
        repo = repo[len('https://github.com/'):]
    if repo.endswith('.git'):
        repo = repo[:-4]
    if not _GITHUB_REPOSITORY.fullmatch(repo):
        return ''
    owner, name = repo.split('/')
    if owner.endswith('-') or name in ('.', '..') or name.startswith('.'):
        return ''
    return repo


def feedback_url(repository, category):
    """Return the direct GitHub issue-form URL, or '' if not configured."""
    repo = normalize_repository(repository)
    templates = {'bug': '01_bug_report.yml', 'feature': '02_feature_request.yml'}
    if not repo or category not in templates:
        return ''
    return f'https://github.com/{repo}/issues/new?template={templates[category]}'


def read_packaged_repository(asset_root):
    """Read a repository identifier intentionally shipped with an LAS release."""
    config = Path(asset_root) / 'assets' / 'feedback.json'
    try:
        data = json.loads(config.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return ''
    return normalize_repository(data.get('repository', '')) if isinstance(data, dict) else ''


def support_diagnostics(app_version, qt_version, pyside_version, packaged=False, os_name=None, architecture=None):
    """No usernames, home paths, IPs, artwork, projects, or environment variables."""
    return '\n'.join([
        'Linux Animation Studio diagnostics (user-copied)',
        f'LAS version: {app_version}',
        f'Operating system: {os_name or platform.system()} {platform.release()}',
        f'Architecture: {architecture or platform.machine()}',
        f'Python: {platform.python_version()}',
        f'Qt: {qt_version}',
        f'PySide6: {pyside_version}',
        f'Installation: {"packaged" if packaged else "source"}',
        'No artwork, project paths, or logs are included.',
    ])
