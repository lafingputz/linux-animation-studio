# Linux Animation Studio v0.26.0

Color Studio, drawing-first startup, dynamic tool icons, and transform selection workflow.

## New in v0.26.0

- **No project at launch:** The welcome view displays **No project open**, **New Project**, and **Open Project**. Closing a project returns to the same welcome view. Editing controls are unavailable until a project opens.
- **Timeline collapsed by default:** The animation timeline starts hidden when you open or create a project. **Show Animation Timeline** expands it; drawing, audio, existing cels, and exports are unaffected.
- **Black as the default brush color:** Newly created documents begin with `#000000`, not `#222222`.
- **Per-project brush color:** New saves include an optional `brush_color` entry in the `.las` v6 manifest. Reopening a project saved with v0.26 restores the brush color. Older projects without this field open with black. The project file format version stays **6**.
- **Color Studio:** Clicking the toolbar color circle opens four tabs: **Disc** (interactive hue ring and saturation/value square), **Harmony** (complementary, analogous, triadic suggestions), **Palettes** (create named palettes and add/select swatches), and **Values** (RGB channels, with a system color picker). A hex input is always visible. User palettes persist in cross-platform Qt `QSettings` and are not stored in project files. Clicking Cancel leaves the canvas brush color unchanged; explicitly saved palettes persist.
- **Dynamic tool feedback:** The compact Brush button displays a small preset-specific symbol or custom stamp. The Eraser button reflects current diameter and the Selection button reflects rectangle, freehand lasso, or polygonal lasso. Icons and tooltips change immediately on selection or keyboard cycling. The status line announces cycling through brush/lasso presets.
- **Transform workflow:** Committing a raster transform by **Apply Transform** or **Enter** clears the raster selection. **Shift+Enter** applies while keeping the selection. **Escape / Cancel** aborts the transform and retains the original selection. Multi-frame timeline selections remain intact throughout.
- **Regression safety:** Existing toolbar layout, brush engine, animations, linked cels, multi-frame editing, Wacom input, Ctrl/Alt mouse-wheel zoom, WAV/MP3 audio, and MP4 export logic were preserved.

## Test checklist

1. **Welcome:** Launch LAS; verify no project is open, and New/Open buttons work. Close a project and confirm the welcome screen reappears.
2. **Timeline:** Create/open a project and verify timeline is initially hidden. Show it, animate, and hide it again.
3. **Default color:** New project starts at `#000000`. Change the color, save as `.las`, reopen, confirm the saved color returns; open a legacy project and check its color defaults safely.
4. **Disc:** Drag hue ring and saturation/value square; choose color; verify the actual brush color and preview.
5. **Harmony:** Try complementary, analogous, and triadic swatches.
6. **Palettes:** Create a palette, save swatches, close/reopen LAS, retrieve swatches; check Cancel does not change canvas color.
7. **Values:** Change RGB channels, enter hex colors, verify synchronization.
8. **Dynamic brush:** B and Shift+B must show an icon for each built-in preset *before* drawing; custom brush should show tip thumbnail.
9. **Dynamic eraser/selection:** Check eraser size icon updates and M, L, Shift+L update marquee/lasso icon immediately.
10. **Transforms:** With lasso selection, Apply/Enter should deselect; Shift+Enter should retain selection; Cancel should retain original selection. Verify grouped timeline frame selection is unaffected.
11. **Small screen:** Check dialog and toolbar on Surface Pro 3. Verify tool panels/timeline don't shift offscreen.
12. **Regression:** Test pressure, brush library, linked cels, multi-frame edits, undo/redo, saving/loading, audio, MP4/PNG export, and Linux/Windows/macOS launch.

This version passed static Python compilation and archive checks, but **Qt graphical behavior still requires hardware acceptance testing**. Back up important projects before using development builds.

## Launch on all three operating systems

After replacing the four repository files and committing them on GitHub:

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

Use the actual cloned repository paths on Windows and macOS. Python virtual environments are OS-specific; do not copy `.venv` between computers. Run `./.venv/bin/python -m pip install -r requirements.txt` on Linux/macOS or `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` on Windows if setting up a new environment.

## Dependencies and platform caveats

- Python 3.12 and PySide6 (`requirements.txt`).
- FFmpeg command-line executable is needed for video export. Install it on the current OS and make it available through `PATH`, or set `LAS_FFMPEG_PATH` to the executable's full path.
- Native launch has been verified in earlier LAS versions on Linux, Windows, and macOS. Tablet pressure has been validated on Linux/Intuos and Windows/Cintiq; macOS/CTH-490 pen input remains unverified due to legacy driver limitations.
- Standalone installers/bundles are not included. `.las` format stays at version 6.
