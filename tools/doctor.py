"""Quick, read-only LAS development-environment diagnostics."""
import os
from pathlib import Path
import platform
import shutil
import sys

def main():
    print('LAS diagnostics')
    print('Platform:', platform.platform())
    print('Python:', sys.version.split()[0])
    print('Python executable:', sys.executable)
    try:
        import PySide6
        print('PySide6:', PySide6.__version__)
    except ImportError as exc:
        print('PySide6: not installed', exc)
    try:
        import PyInstaller
        print('PyInstaller:', PyInstaller.__version__)
    except ImportError:
        print('PyInstaller: not installed (optional for source runs)')
    override = os.environ.get('LAS_FFMPEG_PATH')
    ffmpeg = override if override and Path(override).is_file() else shutil.which('ffmpeg')
    print('FFmpeg:', ffmpeg or 'not found (MP4 export requires FFmpeg)')
    print('LAS_FFMPEG_PATH override:', override or '(unset)')
    print('QT_QPA_PLATFORM:', os.environ.get('QT_QPA_PLATFORM') or '(default)')
    print('Working directory:', Path.cwd())

if __name__ == '__main__':
    main()
