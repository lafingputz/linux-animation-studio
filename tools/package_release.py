"""Experimental OS-native distribution packages from a verified PyInstaller build.
Run on target OS. Requires Inno Setup on Windows / hdiutil on macOS.
Linux generates a user-installable tarball; no root required.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
APP = 'LinuxAnimationStudio'
VERSION = '0.33.0'


def package_plan(root=ROOT, platform=sys.platform):
    root = Path(root)
    from check_build import build_paths
    bundle, binary = build_paths(root, platform)
    out = root / 'releases'
    if platform == 'win32':
        target = out / f'LinuxAnimationStudio-{VERSION}-windows-setup.exe'
        kind = 'inno'
    elif platform == 'darwin':
        target = out / f'LinuxAnimationStudio-{VERSION}-macos.dmg'
        kind = 'dmg'
    else:
        target = out / f'LinuxAnimationStudio-{VERSION}-linux.tar.gz'
        kind = 'tar'
    return kind, bundle, binary, target


def inno_script(bundle, target):
    # Generated on Windows, using native absolute paths.
    source = str(Path(bundle).resolve()).replace('/', '\\')
    icon = str((ROOT / 'assets' / 'las.ico').resolve()).replace('/', '\\')
    out = str(Path(target).parent.resolve()).replace('/', '\\')
    return rf'''[Setup]
AppName=Linux Animation Studio
AppVersion={VERSION}
AppPublisher=Linux Animation Studio
DefaultDirName={{autopf}}\Linux Animation Studio
DefaultGroupName=Linux Animation Studio
OutputDir={out}
OutputBaseFilename=LinuxAnimationStudio-{VERSION}-windows-setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayIcon={{app}}\{APP}.exe
SetupIconFile={icon}

[Files]
Source: "{source}\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\Linux Animation Studio"; Filename: "{{app}}\{APP}.exe"
Name: "{{autodesktop}}\Linux Animation Studio"; Filename: "{{app}}\{APP}.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{{app}}\{APP}.exe"; Description: "Launch Linux Animation Studio"; Flags: nowait postinstall skipifsilent
'''


def package_linux(bundle, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    launcher = '''#!/bin/sh
set -eu
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "$HERE/LinuxAnimationStudio/LinuxAnimationStudio" "$@"
'''
    install = '''#!/bin/sh
set -eu
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/linux-animation-studio"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$DEST" "$APPS" "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
cp -R "$HERE/LinuxAnimationStudio" "$DEST/"
cp "$HERE/las.png" "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps/linux-animation-studio.png"
cat > "$APPS/linux-animation-studio.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Linux Animation Studio
Comment=Free 2D drawing and animation
Exec=$DEST/LinuxAnimationStudio/LinuxAnimationStudio
Icon=linux-animation-studio
Terminal=false
Categories=Graphics;2DGraphics;
EOF
chmod +x "$DEST/LinuxAnimationStudio/LinuxAnimationStudio"
printf 'Installed Linux Animation Studio. Find it in your app launcher.\\n'
'''
    uninstall = '''#!/bin/sh
set -eu
BASE="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -rf "$BASE/linux-animation-studio/LinuxAnimationStudio"
rm -f "$BASE/applications/linux-animation-studio.desktop"
rm -f "$BASE/icons/hicolor/256x256/apps/linux-animation-studio.png"
printf 'Removed LAS executable and launcher; preferences and project files remain untouched.\\n'
'''
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td) / f'LinuxAnimationStudio-{VERSION}-linux'
        stage.mkdir()
        shutil.copytree(bundle, stage / APP)
        for name, content in (('run.sh',launcher),('install.sh',install),('uninstall.sh',uninstall)):
            f = stage / name
            f.write_text(content)
            f.chmod(0o755)
        shutil.copy2(ROOT / 'assets' / 'las.png', stage / 'las.png')
        with tarfile.open(target, 'w:gz') as archive:
            archive.add(stage, arcname=stage.name)


def package_macos(bundle, target):
    if not shutil.which('hdiutil'):
        raise RuntimeError('hdiutil was not found. Build the DMG on macOS.')
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td) / 'LAS Disk Image'
        stage.mkdir()
        shutil.copytree(bundle, stage / bundle.name, symlinks=True)
        (stage / 'Applications').symlink_to('/Applications', target_is_directory=True)
        subprocess.run(['hdiutil','create','-volname','Linux Animation Studio',
                        '-srcfolder',str(stage),'-ov','-format','UDZO',str(target)],check=True)


def main():
    parser = argparse.ArgumentParser(description='Create an experimental installer/DMG/Linux package from dist/.')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    kind, bundle, binary, target = package_plan()
    print(f'Platform: {sys.platform}\nPackage type: {kind}\nInput: {bundle}\nOutput: {target}')
    if args.dry_run:
        return
    from check_build import validate_build
    _, _, issues = validate_build(ROOT)
    if issues:
        parser.error('Build missing/incomplete: ' + '; '.join(issues))
    target.parent.mkdir(exist_ok=True)
    if kind == 'tar':
        package_linux(bundle, target)
    elif kind == 'dmg':
        package_macos(bundle, target)
    else:
        exe = shutil.which('ISCC.exe') or shutil.which('ISCC')
        if exe is None:
            candidates = [Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)')) / 'Inno Setup 6' / 'ISCC.exe',
                          Path(os.environ.get('ProgramFiles','C:/Program Files')) / 'Inno Setup 6' / 'ISCC.exe']
            exe = next((str(p) for p in candidates if p.is_file()), None)
        if not exe:
            parser.error('Inno Setup 6 is required to create Windows installer; install it first.')
        script = ROOT / 'build' / 'LASSetup.iss'
        script.parent.mkdir(exist_ok=True)
        script.write_text(inno_script(bundle, target), encoding='utf-8')
        subprocess.run([exe,str(script)],check=True)
    if not target.is_file():
        raise RuntimeError('Packaging finished without the expected output.')
    print('Package created:',target)
    print('Next: install on a clean OS profile/machine, then test drawing, save/open and exports.')

if __name__ == '__main__':
    main()
