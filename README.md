# Linux Animation Studio v0.30.0

**Dockable Workspaces, Compact Animation Menu & Batch Frames.** Based on the user-tested v0.29.0 source. The `.las` project format remains **v6**, and the existing drawing, Color Studio, playback, exposure, audio, and export functionality is retained.

## What's new

- **Resizable/dockable/floating Timeline, Tools, and Layers:** Native Qt dock widgets are movable by their title bars. Resize from the edges, detach into floating windows, drag to a second monitor, and redock. `View` menu exposes all three panels plus **Reset Workspace Layout**.
- **Independent workspace layouts:** Drawing and Animation continue to use their own saved visibility and now also remember dock positions, sizes, and floating state in local `QSettings`. On startup, the app still opens with no project; Drawing initially hides all three docks, and Animation initially shows the timeline. Floating windows no longer on a connected monitor are redocked when restoring a workspace.
- **Frames + audio visible together:** The audio waveform is now beneath the frame thumbnails instead of inside a mutually exclusive tab. Expand the dock upward to see more of both simultaneously. The Audio tab still contains audio metadata/settings; import/removal, mute, and volume are in the Animation menu.
- **Animation menu:** Frame navigation, playback, blank/duplicate/delete/add-multiple, exposure/hold/link operations, onion ghost range settings, audio, and motion commands have moved into the top-level **Animation** menu. The timeline retains **FPS**, **Go to Frame**, **Loop**, **Onion skins**, and **Ghost opacity** and tabbed track/parameter views. Multi-frame editing is a checkable menu action; the visible status indicator continues to warn when it is active.
- **Batch blank frames:** **Animation → Add Multiple Frames…** accepts a number and a placement choice (after current / append to end). Insertion is one undo step, respects the existing 120-frame limit, shifts later frames and motion-object keyframes, and leaves earlier cels intact. Audio remains aligned to absolute timeline time; inserting frames does **not** automatically time-stretch or reposition an imported audio clip.
- **Customizable shortcuts:** Defaults include `Alt+N` blank, `Alt+D` duplicate, `Alt+Shift+N` multiple frames, `Alt+Backspace` delete, `Shift+P` stop, and existing `P` play/pause, `,` / `.` adjacent frame, `<` / `>` first/last frame. Customize these in **Edit → Keyboard Shortcuts…**. Additional menu commands remain accessible with the mouse and can gain user-defined shortcuts in later releases.
- **Same export and packaging utilities:** PyInstaller helpers and the v0.29 export optimization remain. New dependency-free tests cover a batch-frame insert/undo/redo transaction and dock/menu source wiring.

## Source installation

Replace your tracked source files with the ZIP contents in GitHub, preserving the `tests/` and `tools/` folders. Commit, then pull on each machine. Python 3.12 and your existing virtual environment are recommended.

### Linux / Pop!_OS

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

### Windows / PowerShell

```powershell
cd "C:\path\to\linux-animation-studio"
git pull --ff-only
.\.venv\Scripts\python.exe main.py
```

### macOS / Terminal

```bash
cd /path/to/linux-animation-studio
git pull --ff-only
./.venv/bin/python main.py
```

The Windows/macOS paths are placeholders.

## Verification

```bash
python -m unittest discover -s tests -v
python tools/build.py --dry-run
```

On macOS/Windows, substitute the corresponding venv Python executable if `python` isn't found. Use `python tools/build.py` to create a native app; do so on the target OS. The output remains experimental and needs device-specific verification.

**Local release validation:** Source compiled; lightweight dependency-free tests passed; packaging dry-run passed. The complete test suite's PySide6-dependent project tests and Qt GUI cannot run in the packaging environment because PySide6 was unavailable. Native docking behavior, multiple-monitor restoration, input, audio, and packaged builds must be checked on your devices.

## Suggested v0.30 acceptance checks

1. Startup: no project open; Drawing hides all docks, Animation reveals timeline.
2. Resize timeline vertically: see thumbnail strip and audio waveform simultaneously; drag the dock's edge upward and downward.
3. Float each panel; move timeline to a second Windows monitor; redock the three panels.
4. Customize layouts independently in Drawing/Animation; restart LAS and verify both persist. Disconnect second monitor and confirm recovery.
5. `View → Reset Workspace Layout` should recover a docked, usable default.
6. Test `Tab` Focus Mode with docked/floating panels and verify previous visibility restores.
7. Add multiple blank frames after current and at end, test upper limit of 120, undo/redo in one step, verify motion keyframes shift and that existing art remains.
8. Verify Animation menu covers existing commands, shortcuts can be remapped, and the compact timeline leaves visible FPS, Go to, Loop, Onion Skin, ghost opacity.
9. Test Wacom/mouse input, layers, linked cels, exposure dragging, onion skins, playback, audio sync, `.las` save/load, high-FPS PNG/MP4 exports, cross-platform source launch and packaged builds.

**Status:** v0.30.0 test candidate. Mac pen-tablet pressure remains unverified on supported Mac hardware. Signing/notarization and clean-machine public distribution are not yet validated.
