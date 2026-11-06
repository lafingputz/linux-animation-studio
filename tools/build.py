"""Native PyInstaller build helper. Run on the OS you want to distribute."""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = 'LinuxAnimationStudio'

def destination(binary_dir):
    return binary_dir / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')

def main():
    parser = argparse.ArgumentParser(description='Create a native LAS application with PyInstaller.')
    parser.add_argument('--ffmpeg', type=Path, help='Optional FFmpeg executable to bundle alongside LAS (check license obligations).')
    parser.add_argument('--dry-run', action='store_true', help='Print the intended build command; do not build.')
    args = parser.parse_args()
    if not (ROOT / 'main.py').exists():
        parser.error('main.py missing from project root')
    if args.ffmpeg and not args.ffmpeg.is_file():
        parser.error('FFmpeg path is not a file')
    if not args.dry_run and importlib.util.find_spec('PyInstaller') is None:
        parser.error('PyInstaller not installed. Run: python -m pip install -r requirements-build.txt')
    dist = ROOT / 'dist'
    cmd = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
           '--onedir', '--name', APP, '--distpath', str(dist), '--workpath', str(ROOT / 'build'),
           '--specpath', str(ROOT), str(ROOT / 'main.py')]
    print('Building on:', sys.platform)
    print('Command:', ' '.join(map(str, cmd)))
    if args.dry_run:
        return
    subprocess.run(cmd, cwd=ROOT, check=True)
    if sys.platform == 'darwin':
        # PyInstaller .app bundles place the native executable inside Contents/MacOS.
        binary_dir = dist / (APP + '.app') / 'Contents' / 'MacOS'
        result = dist / (APP + '.app')
    else:
        binary_dir = dist / APP
        result = binary_dir / (APP + ('.exe' if os.name == 'nt' else ''))
    # Validate the native output layout; launching and exporting still require
    # manual tests on the target operating system.
    from check_build import validate_build
    _, _, issues = validate_build(ROOT)
    if issues:
        raise SystemExit('\n'.join(issues))
    if args.ffmpeg:
        output = destination(binary_dir)
        if args.ffmpeg.resolve() != output.resolve():
            shutil.copy2(args.ffmpeg, output)
        if os.name != 'nt':
            output.chmod(output.stat().st_mode | 0o111)
        print('Bundled FFmpeg:', output)
    else:
        print('FFmpeg was not bundled; export needs a system FFmpeg or LAS_FFMPEG_PATH.')
    print('Built:', result)
    print('Distribute the full output folder (or .app), not just the executable.')

if __name__ == '__main__':
    main()
