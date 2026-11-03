# Linux Animation Studio v0.27.0

**Drawing and Animation Workspaces**. This release keeps the v0.26 drawing engine, Color Studio, animation timeline, audio, and `.las` project format intact while adding dedicated layouts for drawing and animation.

## What's new

- **Workspace switcher:** The compact top toolbar offers **Drawing** and **Animation**. Use the drop-down or the configurable **Ctrl+1** / **Ctrl+2** shortcuts.
- **Drawing workspace:** Defaults to the timeline hidden, Tools and Layers panels hidden. This is the default workspace when launching LAS or opening a new session.
- **Animation workspace:** Defaults to the timeline visible, Tools and Layers panels hidden. The timeline, transport, exposure grips, onion skin controls, audio tab and multi-frame edit tools remain available.
- **Independent layout memory:** Each workspace saves the visibility of the timeline, Tools, and Layers panels in cross-platform Qt application preferences. Hide/show a panel, switch away, and return to find your preferred arrangement. These are *per-computer user preferences*, not project content.
- **Non-destructive workspace switching:** The switcher changes the visible layout only. Active frame, layer, drawing color, brush selection, canvas zoom, document state, and audio remain in place. The switch attempts to preserve the canvas-space point in the viewport center when panel geometry changes.
- **Focus Mode:** Tab still hides all controls. Switching workspace exits Focus Mode first, and Tab can be used independently in either layout.
- **No project at launch:** Retains v0.26 welcome screen, New/Open Project buttons, black default brush color, and `.las` v6 compatibility.

## Acceptance checklist

1. **Startup:** LAS launches with no project open; New/Open buttons work. After creating/opening a project, Drawing is selected and the timeline is initially collapsed unless the user's Drawing layout preference was intentionally changed.
2. **Drawing layout:** The canvas has maximum room; expand/collapse Tools, Layers, and Timeline as desired.
3. **Animation layout:** Switch to Animation; timeline appears by default for a first-time user. Frame strip, transport, cels, onion skins, audio, and motion tabs remain usable.
4. **Independent preferences:** In Drawing, show Layers but hide Tools/Timeline. In Animation, show Timeline/Tools but hide Layers. Switch back and forth and verify each workspace restores its own arrangement.
5. **Restart persistence:** Close LAS, reopen a project, and switch between workspaces to confirm both panel arrangements are remembered. Startup mode remains Drawing.
6. **Toolbar and keyboard:** Test the workspace dropdown, Ctrl+1, Ctrl+2, keyboard remapping, and shortcut conflict detection.
7. **State preservation:** On frame 10 at 200% zoom, switch layouts. Verify same frame, selected layer, drawing color, brush and zoom, with no unexpected changes to artwork or playhead.
8. **Focus Mode:** Tab to hide panels and restore them in both workspaces; switch workspace before and after Focus Mode.
9. **Small-screen:** Test Surface Pro 3 layout with panels open and closed; ensure the toolbar, project canvas, and animation timeline remain accessible.
10. **Drawing regression:** Test Wacom pressure on Linux/Windows, lasso/transform, multi-frame edit and grouped undo/redo.
11. **Animation/audio:** Test exposure holds, linked cels, playback, waveform seeking, audio sync, PNG and MP4 export.
12. **Cross-platform:** Launch and switch workspaces on Linux, Windows, and macOS; save and reload a `.las` v6 project.

**Testing status:** Python source compilation and archive integrity checks passed, with targeted headless state-transition tests for workspace preferences. The Qt GUI itself has not been exercised on target hardware in this environment; v0.27 is a testing candidate. Make backups of important projects when trying development builds.

## Setup and launch

Unzip this four-file source package and replace the corresponding files in your GitHub repository. Commit the changes, then pull them on each computer. The `.venv` virtual environment is **not** included and must be created separately per OS.

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

Replace the example Windows and macOS paths with the locations of your repository clones.

### Dependencies and caveats

- Python 3.12 with PySide6; install `requirements.txt` in the platform's virtual environment if needed.
- MP4 export requires a separate FFmpeg CLI executable available via PATH or `LAS_FFMPEG_PATH`.
- `.las` document format is unchanged at v6. UI workspace preferences are stored using `QSettings` on the local machine, not in the `.las` file.
- Mac pen input with the legacy CTH-490 remains unverified because of driver compatibility; macOS mouse and keyboard workflows have been tested previously.
- Standalone `.exe` and `.app` packages are not included.
