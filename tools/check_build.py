"""Validate that a native PyInstaller output exists and is structurally complete.

This is a packaging check, not proof that the app launches on another computer.
"""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = 'LinuxAnimationStudio'


def build_paths(root=ROOT, platform=sys.platform):
    dist = Path(root) / 'dist'
    if platform == 'darwin':
        bundle = dist / f'{APP}.app'
        return bundle, bundle / 'Contents' / 'MacOS' / APP
    folder = dist / APP
    binary = folder / (APP + ('.exe' if platform == 'win32' else ''))
    return folder, binary


def validate_build(root=ROOT, platform=sys.platform):
    bundle, binary = build_paths(root, platform)
    issues = []
    if not bundle.is_dir():
        issues.append(f'Missing application directory: {bundle}')
    if not binary.is_file():
        issues.append(f'Missing application executable: {binary}')
    elif platform != 'win32' and not os.access(binary, os.X_OK):
        issues.append(f'Application executable has no execute permission: {binary}')
    if platform == 'darwin' and not (bundle / 'Contents' / 'Info.plist').is_file():
        issues.append(f'Missing macOS Info.plist: {bundle}')
    return bundle, binary, issues


def main():
    parser = argparse.ArgumentParser(description='Check the output of a native LAS PyInstaller build.')
    parser.add_argument('--root', type=Path, default=ROOT, help='Project root containing dist/')
    args = parser.parse_args()
    bundle, binary, issues = validate_build(args.root)
    print('Application output:', bundle)
    print('Executable:', binary)
    if issues:
        for issue in issues:
            print('ERROR:', issue)
        raise SystemExit(1)
    print('Build structure: OK')
    print('Next: launch the application, then verify open/save, drawing, audio, and exports.')


if __name__ == '__main__':
    main()
