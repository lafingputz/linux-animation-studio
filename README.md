# Linux Animation Studio v0.25.1

Mouse and keyboard usability update, built on the validated v0.25.0 brush library.

## What's new in v0.25.0

- **Canvas-first workspace:** Advanced tool settings and layer management begin collapsed, maximizing drawing room on small displays. Click **⚙ Tools** or **▤ Layers** to show/hide the existing panels. This is intentional: all controls from v0.23 remain available.
- **Compact tool strip:** Brush, Eraser, Selection, Transform, and Pan have concise toolbar buttons with tooltips; selected tool remains visibly checked. Use the small dropdown arrow attached to Brush, Eraser, or Selection for submenus.
- **Quick brush library:** Built-in Round, Pencil, Ink, and Airbrush presets are available from the Brush dropdown with lightweight text-based stroke samples. The full custom brush library, pressure dynamics, stamps, and detailed settings remain in **⚙ Tools**; full graphical previews are planned for the next UI milestone.
- **Eraser presets:** Four quick eraser sizes, retaining independent brush/eraser sizing. The detailed settings panel remains available.
- **Selection submenu:** Rectangle, Freehand Lasso, and Polygonal Lasso are available directly from a dropdown; advanced selection-related operations stay accessible.
- **Simple color swatch:** One colored circle opens Qt's existing color picker. The disc/harmony/palette manager is planned for a subsequent release.
- **Existing File menu and animation timeline remain available**; Undo and Redo are now compact toolbar icons. This release deliberately does not replace the timeline or transform engine.
- **No drawing engine or project format rewrite.** Keep v0.23 portability, multi-frame edit warning, WAV/MP3 playback, exposure holds, and MP4 exporting. `.las` format remains version 6.

## UI notes

The tool buttons show a split arrow for the Brush, Eraser, and Selection submenus. Click the main portion to activate the last selected subtool; click the arrow to choose a preset or selection type. Use **⚙ Tools** for custom brush creation, tuning, transform apply/cancel, and other advanced controls. Use **▤ Layers** to show layer management. The application menu bar continues to provide File, Edit, and other functions. Tab remains Canvas Focus Mode.

## Original compact-toolbar regression checks

1. Start LAS on your Surface Pro 3, Windows Cintiq, and macOS; confirm the sidebar panels begin collapsed, and the drawing canvas has more space.
2. Switch between Brush and Eraser; verify independent sizes and pressure behavior. Choose presets from dropdown arrows.
3. Select Rectangle, Freehand Lasso, and Polygonal Lasso from the Selection dropdown; test drawing within each mask.
4. Test Transform movement, Apply, and Cancel (the last two remain in **⚙ Tools**), Pan, undo/redo, and keyboard shortcuts.
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

## v0.25.0: Brush and Eraser Libraries

- The arrow next to the **Brush** icon opens **Brush Library…**, a compact category-filtered picker with illustrative preview strokes and named built-in presets (Round, Pencil, Ink, Airbrush).
- The **Custom** category lists brushes already saved in LAS's user brush directory, with previews of their stamp tips. Brush creation, editing, and deletion remain accessible through **Advanced Settings…**.
- The arrow next to **Eraser** opens a separate picker of four eraser size presets, with previews. Erasers retain their own diameter, independent of the current drawing brush. These are size presets, not distinct textured eraser engines.
- Recent brush and eraser choices are saved in cross-platform QSettings preferences and restored on the next launch when the brush still exists.
- A double-click or **OK** applies the selected item; **Cancel** closes without changing it. The real canvas engine remains unchanged. Previews are illustrative, not literal pressure simulations.
- `.las` file format remains **version 6**.

### Launch reminders (after git pull)

Linux / Surface Pro 3:
```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```
Windows 11 / PowerShell (replace directory with your clone):
```powershell
cd 'C:\path\to\linux-animation-studio'
git pull --ff-only
.\.venv\Scripts\python.exe main.py
```
macOS / Terminal (replace directory with your clone):
```bash
cd /path/to/linux-animation-studio
git pull --ff-only
./.venv/bin/python main.py
```

## v0.25.1: Mouse Zoom & Keyboard Workflows

- **Ctrl+wheel / Alt+wheel** over the canvas zooms by 15% per wheel notch, constrained to the existing 25%–800% range, with the mouse pointer acting as the zoom anchor. Without modifiers the scroll area continues to scroll. Linux desktop window managers may reserve Alt+wheel, so Ctrl+wheel is the recommended fallback.
- **Shortcut keys**, configurable through **Edit → Keyboard Shortcuts…**:
  - `B` selects Brush; `Shift+B` cycles Round → Pencil → Ink → Airbrush, returning to Round after Airbrush.
  - `E` selects Eraser; `M` selects Rectangle Marquee.
  - `L` selects Freehand Lasso; `Shift+L` toggles Freehand/Polygonal Lasso.
  - `T` selects Transform, `H` selects Hand/Pan.
  - `Space+drag` remains temporary canvas panning, `P` playback, `,` / `.` frame navigation, `<` / `>` first/last frame, and `Ctrl+0` fit canvas.
- Tool-key callbacks avoid switching tools while entering text or numeric values into editing widgets; custom shortcuts remain persistent and conflict-checked.
- The **Move** button is removed from the toolbar; **Transform** handles moving artwork as well as scale/rotate. Internal Move functionality remains for compatibility, with no changes to actual transformations, undo/redo, or `.las` format v6.
- **Mouse-wheel zoom is canvas-only** so timeline, brush library, and other scrollable panels retain normal wheel behavior.

### v0.25.1 quick acceptance tests

1. Test Ctrl+wheel and Alt+wheel over the canvas at several zoom levels and near canvas corners. Verify pointer-centered zoom, 25%/800% limits, and normal unmodified scrolling.
2. Verify B, Shift+B, E, M, L, Shift+L, T, H, and visually checked tool buttons.
3. Verify shortcut customizations persist after restart and conflicts are rejected.
4. Type letters in a layer rename dialog and numeric inputs; they must not switch tools.
5. Transform selected artwork and entire active cel; verify Apply/Cancel, undo/redo.
6. Check Wacom pressure and Space+drag pan; test mouse middle-button pan where available.
7. Regression: brush library, custom stamps, selections, linked cels, multi-frame edits, audio/MP4, projects, Windows/macOS launch.

### Launch on each OS (after replacing files in GitHub and pulling)

**Linux (Surface Pro 3):**
```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

**Windows (PowerShell):**
```powershell
cd "C:\path\to\linux-animation-studio"
git pull --ff-only
.\.venv\Scripts\python.exe main.py
```

**macOS (M1 MacBook Air):**
```bash
cd /path/to/linux-animation-studio
git pull --ff-only
./.venv/bin/python main.py
```

macOS tablet pressure remains unverified due to the older CTH-490 driver's OS support, not a confirmed LAS regression.
