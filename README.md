# Linux Animation Studio v0.29.0

**Performance & distribution polish.** Built from the tested v0.28.1 source. This release optimizes repeated-frame animation export, adds native-build verification, and preserves the established drawing, audio, animation, workspace, and Color Studio workflows. The `.las` project format remains **version 6**.

## What's new

- **Faster export when increasing FPS:** If a source frame must appear multiple times in an exported PNG sequence or MP4 frame sequence (for example, 12 FPS to 24 FPS), LAS now renders/encodes the source frame **once** and copies the encoded PNG for repeated output frames. All numbered output files still exist. The optimization has no effect on exports where output source frames are unique. Speedups are workload- and disk-dependent and have **not** been benchmarked on actual hardware here.
- **Pure export frame-mapping helper:** `source_frame_for_export()` preserves the old frame-time mapping; four dependency-free tests cover higher/lower/uneven FPS and invalid input. No motion interpolation or audio timing changes are introduced.
- **Standalone build verification:** `tools/check_build.py` checks the expected executable/bundle path and macOS Info.plist, and `tools/build.py` automatically performs these checks after PyInstaller builds. This validates structure, **not** runtime correctness, FFmpeg operation, signing, or clean-machine support.
- **Packaging layout tests:** Three new lightweight tests cover cross-platform expected paths and missing-build detection.
- **Existing tools retained:** Diagnostics, repeatable canvas composite benchmark, PyInstaller helper, and source/project tests remain available.
- **Qt stylesheet fix retained:** The warning addressed in v0.28.1 is still covered by its dedicated regression test.

## Verification and limitations

- Python syntax/compilation, release-structure tests, export mapping tests, build-layout tests, and build dry-run passed in the packaging environment.
- **PySide6 was unavailable in that environment**, so `tests/test_project_compat.py`, the GUI, standalone native packaging, and real performance measurements must be verified on your computers.
- Mac pen pressure remains unverified on supported tablet hardware. Windows/Linux pressure testing should be repeated in the normal regression pass.
- Do not distribute packaged applications publicly without checking licensing (especially FFmpeg), code signing/notarization, and clean-machine dependencies.

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

The compatibility test module sets `QT_QPA_PLATFORM=offscreen` by default, suitable for headless smoke testing on systems with the required Qt platform plugins. Offscreen rendering is not an alternative to testing a real pen or GUI. Compare benchmark numbers only on the same machine, Qt version, and OS. Performance measurements for canvas compositing remain the same baseline; this release optimizes repeated export frames only.

## v0.29 acceptance tests

1. Source launch on Linux, Windows, macOS; ensure no Qt stylesheet warnings.
2. Create/open/save `.las` projects; preserve brush color, frame and workspace state.
3. Verify PNG sequence export at the **same** FPS and **higher** FPS (12→24), and compare repeated frames visually.
4. Verify **lower** FPS (24→12) and **uneven** FPS (10→15) sequence exports.
5. Export MP4 with embedded audio; check audio stays synchronized after FPS conversion.
6. Run `python -m unittest discover -s tests -v` using the LAS virtual environment.
7. Run `python tools/benchmark.py` and compare to your v0.28 baseline on the same machine/settings.
8. Build standalone apps on each OS using `python tools/build.py`; run `python tools/check_build.py`.
9. Launch the native application and check drawing, Color Studio, timeline, save/load, and MP4 export.
10. Retest Wacom pressure, selection/transform, multi-frame editing, onion skinning, and compact Surface UI.

**Status:** v0.29.0 test candidate; `.las` format is unchanged (v6).
