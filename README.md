# Linux Animation Studio v0.32.0

**Timeline Performance & Reliability** (testing candidate). Built on the validated v0.31.0 source with the `.las` project format **unchanged at version 6**.

## What's new in v0.32

- **Bounded timeline thumbnail cache:** Refreshing the timeline reuses 90×60 thumbnails for unchanged cels instead of compositing every full-size frame each time. Up to 128 thumbnails are retained (the maximum project timeline remains 120 frames), so a complete 120-frame refresh can benefit from the cache.
- **Automatic visual invalidation:** Raster image changes are detected using Qt `QImage.cacheKey()`; layer visibility/opacity and motion transforms are included in the cache signature. A live motion-transform preview bypasses the cache, and opening or creating a project clears old thumbnails. Linked cel edits and undo/redo should refresh correctly.
- **Performance diagnostics:** `python tools/benchmark_timeline.py` measures cold and warm 120-frame thumbnail passes and a single-frame edit at 1200×800. `tools/benchmark.py` remains unchanged for canvas compositing. Tests cover thumbnail caching and invalidation.
- **Scope:** This release avoids changes to painting, audio synchronization, playback timing, project serialization, or installer architecture. These systems remain subject to regression testing. There is **no claimed measured speedup** until benchmarked on your machines.

## Existing features preserved



- **Recent Projects:** Welcome screen retains New/Open and displays up to 12 recently opened or saved `.las` files. Double-click a recent project, or select it and choose **Open Selected**. Missing files are flagged; you can remove an entry without deleting the actual document, or clear the whole list after confirmation. The list lives in your device-local `QSettings` preferences, not in `.las` project files.
- **App identity:** A consistent LAS app icon is included in the source and passed to PyInstaller for native application shortcuts, window icons and packaged builds; the program still identifies its version in About and the title bar.
- **Installer packaging:** New `tools/package_release.py` builds a Windows Inno Setup 6 installer (`.exe`), a macOS drag-to-Applications `.dmg` with `hdiutil`, or a portable Linux `.tar.gz` with optional per-user desktop installer/uninstaller scripts. Packaging must be run *on the target OS* after `tools/build.py`, using local native tools. None of the release packages are signed/notarized.
- **Diagnostics:** Existing `tools/doctor.py`, packaging verification, automated `.las` regression tests and performance benchmarking are preserved. The new distribution checks cover installer plans and asset presence.
- **Compatibility:** Existing Wayland panel grips, resizable/floating docks, independent workspaces, Color Studio, Wacom drawing, frame/audio tools, import and export logic are unchanged.

## Project source setup

Extract **all** ZIP files and directories to your GitHub project, preserving `assets/`, `tests/` and `tools/`.

### Linux / Surface Pro 3

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

### Windows 11 / PowerShell

```powershell
cd "C:\path\to\linux-animation-studio"
git pull --ff-only
.\.venv\Scripts\python.exe main.py
```

### macOS / Apple Silicon

```bash
cd /path/to/linux-animation-studio
git pull --ff-only
./.venv/bin/python main.py
```

Change example paths to match your repository.

## Build and package

Use your virtual environment's Python, substituting `./.venv/bin/python` on macOS or `.\.venv\Scripts\python.exe` on Windows:

```bash
python -m pip install -r requirements-build.txt
python tools/doctor.py
python -m unittest discover -s tests -v
python tools/build.py --dry-run
python tools/build.py
python tools/check_build.py
python tools/package_release.py --dry-run
python tools/package_release.py
```

**Windows:** Requires **Inno Setup 6**, specifically `ISCC.exe` on PATH or in its normal Program Files location. Output: `releases/LinuxAnimationStudio-0.32.0-windows-setup.exe`. The installer includes Start Menu and optional desktop shortcuts and supports uninstall. It does not sign the executable or automatically bundle FFmpeg.

**macOS:** Uses built-in `hdiutil` and outputs `releases/LinuxAnimationStudio-0.32.0-macos.dmg`. Open the disk image and drag the `.app` into `/Applications`. Unsigned applications may be blocked by Gatekeeper; test carefully in a local account. Apple developer signing/notarization is **not provided**.

**Linux:** Outputs `releases/LinuxAnimationStudio-0.32.0-linux.tar.gz` containing the native folder build, `run.sh`, `install.sh`, `uninstall.sh` and icon. Extract and run `./run.sh` to launch without installation, or `./install.sh` to install in the current user's `~/.local/share/` and create an applications-menu launcher. `./uninstall.sh` removes the local app/launcher and leaves preference and project data intact. This is an installable archive, **not an AppImage or system `.deb`**.

**FFmpeg:** System FFmpeg or `LAS_FFMPEG_PATH` may be required for MP4 exports. `tools/build.py --ffmpeg /path/to/ffmpeg` can bundle a supplied executable; check redistribution/license conditions before publishing. Test FFmpeg independently on each build.

**Clean-machine verification:** Copy packages to a separate clean user account or OS machine without your Python virtual environment; confirm launching, saving/opening `.las`, audio, exports, uninstall and absence of missing dynamic libraries. Packaging checks only verify structure, not that these workflows succeed.

## Acceptance test suggestions

1. Fresh launch with no project; New/Open; recent projects empty on first use and populate after first save/open.
2. Save two files, restart, reopen via recent list. Oldest-first? Confirm most recent appears at top and no duplicates on repeated openings.
3. Rename/move a project externally; verify missing-file status and removal don't delete any files.
4. Open a malformed or unsupported `.las`; expect a useful error, no silently lost existing artwork.
5. Test your previous dock layout and animation tools, shortcuts, color palettes, waveform, MP4 audio and Wacom pressure.
6. Run full unittest suite; report results. Build the native app and the installer/package on each OS.
7. Install from the native package (not source directory), launch without Python env, test opening and editing projects, export MP4 using FFmpeg.
8. Test uninstall on Windows/Linux and moving the macOS app into Applications. Verify project data and brushes are preserved.

## Verification status

Python static compilation and dependency-free test suites can run without PySide6. GUI tests and the native packaging processes must be executed on the corresponding OS and remain pending until user hardware testing. No signing/notarization or cross-platform distribution guarantees are implied.
