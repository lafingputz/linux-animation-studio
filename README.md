# Linux Animation Studio v0.24.0

First compact-interface release, built directly on the cross-platform v0.23.0 baseline.

## What's new in v0.24.0

- **Canvas-first workspace:** Advanced tool settings and layer management begin collapsed, maximizing drawing room on small displays. Click **⚙ Tools** or **▤ Layers** to show/hide the existing panels. This is intentional: all controls from v0.23 remain available.
- **Compact tool strip:** Brush, Eraser, Selection, Move, Transform, and Pan have concise toolbar buttons with tooltips; selected tool remains visibly checked. Use the small dropdown arrow attached to Brush, Eraser, or Selection for submenus.
- **Quick brush library:** Built-in Round, Pencil, Ink, and Airbrush presets are available from the Brush dropdown with lightweight text-based stroke samples. The full custom brush library, pressure dynamics, stamps, and detailed settings remain in **⚙ Tools**; full graphical previews are planned for the next UI milestone.
- **Eraser presets:** Four quick eraser sizes, retaining independent brush/eraser sizing. The detailed settings panel remains available.
- **Selection submenu:** Rectangle, Freehand Lasso, and Polygonal Lasso are available directly from a dropdown; advanced selection-related operations stay accessible.
- **Simple color swatch:** One colored circle opens Qt's existing color picker. The disc/harmony/palette manager is planned for a subsequent release.
- **Existing File menu and animation timeline remain available**; Undo and Redo are now compact toolbar icons. This release deliberately does not replace the timeline or transform engine.
- **No drawing engine or project format rewrite.** Keep v0.23 portability, multi-frame edit warning, WAV/MP3 playback, exposure holds, and MP4 exporting. `.las` format remains version 6.

## UI notes

The tool buttons show a split arrow for the Brush, Eraser, and Selection submenus. Click the main portion to activate the last selected subtool; click the arrow to choose a preset or selection type. Use **⚙ Tools** for custom brush creation, tuning, transform apply/cancel, and other advanced controls. Use **▤ Layers** to show layer management. The application menu bar continues to provide File, Edit, and other functions. Tab remains Canvas Focus Mode.

## Recommended v0.24 checks

1. Start LAS on your Surface Pro 3, Windows Cintiq, and macOS; confirm the sidebar panels begin collapsed, and the drawing canvas has more space.
2. Switch between Brush and Eraser; verify independent sizes and pressure behavior. Choose presets from dropdown arrows.
3. Select Rectangle, Freehand Lasso, and Polygonal Lasso from the Selection dropdown; test drawing within each mask.
4. Test Transform, Apply, and Cancel (the last two remain in **⚙ Tools**), Move, Pan, undo/redo, and keyboard shortcuts.
5. Open and close **⚙ Tools** and **▤ Layers**; exercise custom brush controls and layer behavior.
6. Change the color via the swatch, save/reopen a `.las` project, then export PNG/MP4 with audio.
7. Verify animation, exposure holds, linked cels, multi-frame editing, waveform dragging, and Focus Mode did not regress.

## Run from source (Linux, Windows or macOS)

Install Python 3, create a virtual environment, and install the requirements:

```sh
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Activate the environment before installing/running if desired. On Linux/macOS: `source .venv/bin/activate`; on Windows PowerShell: `.venv\\Scripts\\Activate.ps1`. If `python` maps to a different installation, use `python3` or the Windows `py` launcher.

**For the existing Surface Pro 3 workflow:** keep your existing repository and `.venv`, pull the latest commit, then `python main.py` as before.

FFmpeg must be separately installed for MP3 waveform decoding and MP4 export, unless an executable has been provided alongside the application. Put it on `PATH` or set `LAS_FFMPEG_PATH` to the executable (for example, on Windows, `C:\\ffmpeg\\bin\\ffmpeg.exe`). Audio playback uses Qt Multimedia and depends on codecs available in the target environment.

## Experimental builds (not prebuilt binaries)

Packaging requires building **on each target OS** with matching Python/PySide6 architecture. PyInstaller is one possible development packaging option:

```sh
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --name LinuxAnimationStudio main.py
```

Test the `dist/LinuxAnimationStudio` output on the **same target operating system**. On macOS the output may be an `.app` bundle; on Windows an executable directory. Do not assume an archive built on Linux will run on Windows or macOS. Bundling FFmpeg requires separate binary distribution and licensing review. Public macOS releases also need appropriate signing/notarization. These builds are experimental; installers, signing, and shipping standalone binaries are **not** included in this four-file source ZIP.

## Cross-platform acceptance tests

1. **Linux:** existing brush presets and `.las` files load in place; check all v0.22 editing and audio regressions.
2. **Windows/macOS:** launch from source; create a project, draw, save/reopen; check tablet pressure and event handling on connected pen hardware.
3. **Keyboard:** verify Cmd/Ctrl conventions and saved custom shortcuts, including Space+drag, playback, and Focus Mode.
4. **Audio:** import WAV/MP3, seek/play, save/reopen the embedded track, export MP4 with FFmpeg available.
5. **Display:** check Wacom/canvas alignment at 100%, 200%, and high-DPI/Retina scaling; window resize and timeline behavior.
6. **Portability:** transfer an embedded-audio `.las` v6 project between operating systems and validate drawings, cel relationships, and playback.
7. **Mode awareness:** choose multiple frames, enable Multi-frame Edit, confirm orange label stays visible while switching tabs, then disable it.
8. **Packaging:** optionally build and launch a PyInstaller development bundle on Windows/macOS; confirm resource paths and FFmpeg behavior.

## Known limitations

- Windows and macOS **have not yet been run or hardware-tested** for this build. Tablet drivers and Qt Multimedia backend availability vary.
- Qt6 supports high-DPI scaling, but alignment on actual Retina/Windows fractional-scaling hardware needs testing.
- Multi-frame Edit remains opt-in to protect against accidental changes to several drawings.
- Audible scrubbing is not implemented; waveform dragging seeks the timeline.
- This release preserves the single-file `main.py` source architecture. Modularization remains future work.
- `.las` format version 6 may not be readable by older app releases. Backup important projects before editing them with a development build.
