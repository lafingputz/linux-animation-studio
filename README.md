# Linux Animation Studio v0.28.0

**Maintenance, diagnostics, and experimental native packaging.** Based directly on the user-tested v0.27.1 source. The drawing engine, animation functionality, workspace layout model, and `.las` document format (v6) have not been intentionally changed.

## What's changed

- **Qt warning cleanup:** Replaced `palette(mid)` in the shared toolbar color button's stylesheet with a literal `#888888` border color. This is the suspected source of `Could not parse stylesheet of object QPushButton(...)` after Color Studio confirmation, creating a project, and closing/discarding one. Verify on Windows PowerShell; no runtime GUI validation was possible in this build environment.
- **Experimental native packaging helper:** `tools/build.py` invokes PyInstaller on the *current operating system* to build a one-directory application. Windows builds contain an `.exe`, macOS builds an `.app`, and Linux builds an executable in an application folder. Packaging is **not** cross-platform: run the script separately on each OS.
- **Optional FFmpeg sidecar:** `--ffmpeg /path/to/ffmpeg` copies a legal-to-redistribute FFmpeg executable beside the bundled app so MP4 export can locate it. Without bundling, users can install FFmpeg system-wide or set `LAS_FFMPEG_PATH`.
- **Project compatibility smoke tests:** `tests/test_project_compat.py` generates tiny legacy format fixtures for `.las` v1–v6, tests v6 save/reopen, and rejects an invalid project without replacing the current document. These are *new tests*, not a claim that all historical projects have been tested.
- **Developer diagnostics:** `tools/doctor.py` prints Python, PySide6, PyInstaller, FFmpeg, OS, and Qt platform configuration.
- **Performance baseline:** `tools/benchmark.py` measures a repeatable 1200×800 canvas composite to establish a baseline before attempting optimizations. No unverified drawing engine speedup is claimed for this release.
- Expanded `.gitignore` so local PyInstaller build products don't get committed.

## Source install and launch

Replace the project files with the ZIP contents in your GitHub repository and commit them. The ZIP contains no virtual environments or build artifacts. Continue to use your existing Python 3.12 environment.

### Linux (Surface Pro 3 / Pop!_OS)

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

### Windows 11 (PowerShell)

```powershell
cd "C:\path\to\linux-animation-studio"
git pull --ff-only
.\.venv\Scripts\python.exe main.py
```

### macOS (M1 MacBook Air)

```bash
cd /path/to/linux-animation-studio
git pull --ff-only
./.venv/bin/python main.py
```

Use the actual clone paths on Windows/macOS.

## Build a native app (experimental)

In your activated virtual environment, from the repository root:

```bash
python -m pip install -r requirements-build.txt
python tools/doctor.py
python tools/build.py
```

Optional: `python tools/build.py --ffmpeg /absolute/path/to/ffmpeg` to bundle an executable you are permitted to redistribute. Check FFmpeg build, licensing, and any dependent libraries before distributing. `python tools/build.py --dry-run` prints the command without building.

**Output:**

- Windows: `dist/LinuxAnimationStudio/` with `LinuxAnimationStudio.exe`. Distribute the **entire folder**, not the `.exe` alone.
- Linux: `dist/LinuxAnimationStudio/` with `LinuxAnimationStudio`. Distribute the entire folder. Native builds may depend on the target distro's system libraries; test on your Pop!_OS device.
- macOS: `dist/LinuxAnimationStudio.app`. The unsigned app may be blocked by Gatekeeper on other computers; signing and notarization are outside this experimental release. On the build Mac, check that the app starts and the file dialogs, audio, and export functions work.

**Bundled FFmpeg limitations:** FFmpeg may require extra libraries, depending on how it was built. MP4 export requires a working FFmpeg executable even if the LAS application itself launches successfully. Do not assume FFmpeg works solely because it has been copied next to LAS.

## Automated tests and baseline measurement

From the project root with PySide6 installed:

```bash
python -m unittest discover -s tests -v
python tools/benchmark.py
```

The compatibility test module sets `QT_QPA_PLATFORM=offscreen` by default, suitable for headless smoke testing on systems with the required Qt platform plugins. Offscreen rendering is not an alternative to testing a real pen or GUI. Compare benchmark numbers only on the same machine, Qt version, and OS. Performance optimization comes after collecting representative measurements.

## v0.28 acceptance tests

1. Open Color Studio, change the color, press OK, and check PowerShell for the former stylesheet warning.
2. Create a project and close/discard it, checking for the same warning.
3. Verify palette contents, adding/removing colors, and persistence.
4. Run `python -m unittest discover -s tests -v`; check legacy v1–v6 smoke fixtures and v6 roundtrip.
5. Run `python tools/doctor.py` and confirm correct Python, PySide6, and FFmpeg diagnostics.
6. Run `python tools/benchmark.py`; note baseline numbers for future comparison.
7. Run `python tools/build.py --dry-run` on all three OSs.
8. Build using PyInstaller on Windows, Linux, and macOS; check that the native application launches (test on each OS separately).
9. Exercise drawing, pen pressure where supported, workspaces, save/reopen, animation playback, and audio in native builds.
10. Verify PNG, PNG sequence, and MP4 export, with a usable FFmpeg executable.
11. Recheck the Surface Pro 3 small-screen layouts, tool icons, color studio, and Canvas Focus Mode.
12. Confirm existing `.las` projects still open and save correctly after updating.

**Status:** Source syntax checks, ZIP-integrity checks, and available lightweight tests are completed at packaging time. Real GUI behavior and native PyInstaller builds must be tested on Linux, Windows, and macOS. The `.las` document format remains **version 6**. macOS pen tablet functionality remains unverified because the older Wacom hardware/driver isn't supported on that machine.
