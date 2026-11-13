# Linux Animation Studio v0.35.2

**Input & Workflow Stabilization** (test candidate). Built on validated v0.34.1. LAS `.las` format **remains v6**. Existing drawing, animation, audio, packaging, Paint Bucket and GitHub feedback tools are retained.

## New in v0.35.2: Tablet Context Menu Hotfix

- Avoids nested canvas context menus when Wacom tablet buttons generate duplicate event paths.
- Uses non-blocking popup handling and allows only one canvas menu at a time.
- Preserves v0.35.1 brush switching and layer visibility fixes.

## Changes retained from v0.35.1: Input & Workflow Stabilization

- **Wacom/tablet side-button handling:** ignore non-primary tablet presses for painting; route right-button tablet presses to Brush/Eraser context menus. Guards against synthetic secondary-button mouse events. **Must be validated on Windows Cintiq, Linux Wacom, and macOS Apple Pencil.**
- **Built-in brush re-selection:** selecting a built-in preset clears any custom-stamp selection even if the built-in combo box already shows the requested preset. Preset preview and cached stamp state update.
- **Layer eye long-press:** consume the matching release and movement events so holding the eye does not select the layer row.
- **Deletion warning:** the v0.35 source already says deletion *can* be undone. If a tester still sees the opposite message, confirm that the running build is 0.35.2 and report the exact menu/dialog wording.
- **No format change:** `.las` v6 unchanged.

### v0.35.2 focused retest

1. **Windows / Cintiq:** using the pen's right-click side button, open Brush and Eraser menus both hovering and touching. Verify no dots or strokes are drawn. Verify ordinary pen-tip drawing, erasing, and pressure remain intact.
2. **Linux / Wacom:** switch Custom → Round/Pencil/Ink/Airbrush using both the toolbar and canvas menus, including when the built-in combo already displays the target. Confirm the custom stamp no longer draws.
3. **Windows / Cintiq:** hold a layer eye for 1–2 seconds and release. The visibility changes but the active layer does not. Repeat with a quick click, mouse and macOS Sidecar Apple Pencil.
4. **All OS:** delete a populated layer, Undo, then Redo; confirm the warning wording and restored frames/cels. Confirm old `.las` projects still open correctly.
5. Run all automated tests, full draw/animate/export regression, and installer smoke tests before marking issues #3/#4 complete.

## Previous v0.35.0: Layers & Workflow Overhaul

- **Clickable eye icons on every layer:** show/hide an individual layer without changing the selected painting layer; toggling visibility uses the existing undo/redo history.
- **Compact Layers toolbar:** icon buttons for Add Layer, Move Up, Move Down and Delete. Rename and visibility commands now live in the layer's context menu or eye control instead of long button rows. Delete asks for confirmation.
- **Layers right-click:** Rename, Show/Hide, Move Up, Move Down, Delete. The chosen layer becomes active when opening its menu. A reference-layer command is deferred until reference-aware filling is implemented in v0.36.
- **Canvas right-click:** when Brush or Eraser is selected, opens presets/library access, common brush or eraser sizes, brush opacity presets, and advanced settings. Right-click must not paint or erase artwork.
- **Timeline right-click:** frame commands (add blank, duplicate, add multiple, delete, extend holds, split, link from and unlink), plus direct multi-frame Link / Unlink / Break when several frames are selected. A click within an existing multiple selection should preserve the selected range.
- **Multi-frame Edit:** a clearly labeled toggle appears next to the timeline's status indicator and stays synchronized with the Animation menu option; off remains the default.
- **Project compatibility:** `.las` file format remains version 6; no new drawing engine or serialized layer attributes.
- **Distribution:** `/releases/` is ignored by Git so the generated installers are published as GitHub Release assets, not as source changes.

**Not in v0.35:** Reference All Visible Layers and designated reference-layer filling are planned for v0.36, alongside improvements to Paint Bucket edges. Heavy playback on the older Surface Pro 3 remains a separate optimization target.

### v0.35 hands-on verification checklist

1. On each platform, toggle the eye icon beside a **non-active** layer. Ensure its visibility changes while the active painting layer remains unchanged; test Undo and Redo.
2. Add, reorder and delete layers using compact controls. Right-click another layer to rename it, move it, show/hide it, and delete with confirmation. Ensure layer ordering and selection remain correct across frames.
3. Right-click the canvas with Brush selected: see presets/library, size, opacity and Advanced Settings. Choose options and verify they take effect. Repeat with Eraser. Right-click must not leave a mark.
4. Select multiple frames using Shift/Ctrl, then right-click a selected frame. The selected range should remain intact. Test Link Selected, Unlink Selected and Break Selected; verify each operation undoes in one step and refuses to overwrite independent artwork unexpectedly.
5. Use frame context actions for add, duplicate, delete, link and exposure holds. Test on the first/last frame and during playback. Verify no accidental edits happen when a menu is dismissed.
6. Toggle Multi-frame Edit beside the status indicator; confirm it stays synchronized with the Animation menu and that edits affect only selected frames when on.
7. Regression-test brush and eraser, bucket, Color Studio, selection clearing, animation, audio, export and `.las` save/reopen. Run `python -m unittest discover -s tests -v` and build each OS installer.


## Previous: v0.34.1 Paint Bucket performance and visual polish

- **Paint Bucket (G):** click inside an enclosed region on the active raster layer to fill it using the current Color Studio color.
- **Tolerance (0–255):** controls acceptable difference per straight RGBA channel; defaults to 24.
- **Contiguous toggle:** fill only connected pixels, or all matching pixels in the current cel.
- **Selection-aware:** rectangle and lasso selection masks limit region traversal, with antialiased selection edges respected when applying color.
- **Undo/redo:** each fill is one history action, including linked exposures, static layers and explicitly enabled multi-frame editing.
- **Timeline previews:** cache invalidation and thumbnail refresh follow existing cel replacement history.
- **No project format change:** `.las` stays at version 6.

**Scope:** this version samples the active layer only. "Reference All Visible Layers," edge expansion and advanced fill antialiasing are deferred for later improvements. Pick a visible raster layer with a closed outline, select Paint Bucket (G), choose a color, and click inside.


### Improvements in v0.34.1

- **Proper bucket toolbar icon:** a dedicated vector-drawn bucket replaces the generic square.
- **Visible custom bucket cursor:** a high-contrast bucket and precise hotspot remain visible on the canvas, even during a slow fill.
- **Faster flood-fill search:** horizontal-span traversal and fewer repeated pixel comparisons. The fill semantics, selections, global/contiguous behavior, and undoable cel replacement are unchanged.
- **Corrected multi-frame unit test:** explicitly returns the playhead to frame zero before checking opt-in editing.
- **New baseline:** `python tools/benchmark_fill.py` checks a full transparent 1200×800 canvas using contiguous and global fills. Compare results on the same machine against v0.34 and test responsiveness interactively.
- **Project compatibility:** `.las` format remains version 6; no changes to project storage.

### Quick verification for v0.34.1

1. Confirm the toolbar shows a real bucket icon, and the bucket cursor has a visible crosshair aligned with the click point. Draw a closed outline on a raster layer, choose Paint Bucket (G), select a color, and click inside. Inside changes; outside does not.
2. Change tolerance and confirm higher tolerance accepts nearby colors. Toggle Contiguous and compare connected versus global matching pixels.
3. Test rectangle, freehand-lasso and polygonal-lasso selections; no filling may escape selection edges.
4. Check Undo, Redo, independent cels, linked cels, static layers and multi-frame edit on/off.
5. Verify timeline thumbnails refresh after a fill, and `.las` save/reopen retains the result.
6. Run `python tools/benchmark_fill.py` on Linux, Windows, and macOS, especially the Surface Pro 3. Regression-test brush/eraser input, Color Studio, animation, audio, export and three platform installers.

## Previous: v0.33.1 Selection Clearing & Clear Layer

- **Delete** or **Backspace** clears only the selected pixels of the active raster cel. If nothing is selected, neither key erases artwork.
- **Edit → Clear Selected Pixels** provides a menu alternative.
- **Edit → Clear Active Cel / Layer** clears the entire current cel, regardless of selection. Static layers intentionally clear across all frames because their artwork is shared.
- Undo/redo handles clearing in one step and restores **all linked exposures** together.
- Multi-frame Edit operates on selected frames only when explicitly enabled. Repeated linked exposures are edited once.
- Rectangle and lasso selections preserve their clipping masks, including antialiased edges; edits invalidate timeline thumbnails.
- Both deletion shortcuts can be customized under **Edit → Keyboard Shortcuts**. Text inputs are protected from those shortcuts.
- The GitHub reporting destination remains `lafingputz/linux-animation-studio`. Project format is still `.las` v6.

### Previous-version selection clearing checks

1. Draw on the active cel, Ctrl+A, press Delete, Undo and Redo; repeat with Backspace.
2. Select a small rectangle or freehand lasso and delete only that area's pixels.
3. With no selection, pressing Delete does nothing to artwork.
4. Edit → Clear Active Cel / Layer clears the entire active cel and is undoable, including from a partial selection.
5. Unlinked frame cels remain unchanged; linked exposures and static layers clear together and undo together.
6. Enable Multi-frame Edit with multiple frames selected, clear, and undo as one step. Disable it and verify only the active cel changes.
7. Open a text entry field (such as a brush name/number) and verify Delete/Backspace edit text rather than artwork.
8. Check that thumbnail caching, drawing, audio, export, saving/opening `.las` v6, and native packaging still work on all three desktop platforms.

## New in v0.33

- GitHub **Bug report** and **Feature request** issue forms in `.github/ISSUE_TEMPLATE/`. Bug reports request the LAS version, operating system, steps to reproduce, expected/actual behavior, and optional screenshots/diagnostics. Feature requests ask which workflow needs improving and what the proposed solution should do.
- New **Help → Report a Bug…** and **Help → Request a Feature…** menu actions open the appropriate GitHub issue form in the user's default browser. No automatic issue creation or data uploads.
- New **Help → Copy System Information…** dialog displays LAS version, OS, architecture, Python, Qt, PySide6, and source/packaged status. Information is placed on the clipboard **only** when the user clicks the Copy button. No username, home directory, path to projects, IP address, artwork, or error logs are collected.
- New **Help → Configure Feedback Repository…** lets a tester or developer change the issue-tracker destination locally. The configured destination is stored in application preferences, not inside `.las` files. Feedback links accept canonical GitHub `owner/repo` identifiers only.
- The Windows test-suite UTF-8 decoding issue in `tests/test_distribution31.py` is corrected.
- Existing v0.32 thumbnail caching, dockable workspaces, Color Studio, frame tools, installers, and compatibility tests are preserved.

## GitHub repository preconfigured

LAS feedback links now default to the official repository **`lafingputz/linux-animation-studio`**. You do **not** need to edit `assets/feedback.json` before packaging this release or future releases that retain this setting:

```json
{
  "repository": "lafingputz/linux-animation-studio"
}
```

The `tools/build.py` PyInstaller helper includes the `assets/` directory in native builds. An existing user-specific choice made through **Help → Configure Feedback Repository…** takes precedence over the bundled default; users who previously changed the destination can restore the official repository there.

- Bug reports: `https://github.com/lafingputz/linux-animation-studio/issues/new?template=01_bug_report.yml`
- Feature requests: `https://github.com/lafingputz/linux-animation-studio/issues/new?template=02_feature_request.yml`

### GitHub setup

1. Commit **the entire `.github/ISSUE_TEMPLATE/` directory**, including both `.yml` forms and `config.yml`, to your repository's **default branch**. Some GitHub upload interfaces hide dot-folders, so check carefully.
2. In GitHub repository **Settings → General → Features**, ensure **Issues** is enabled. For ordinary outside beta testers to create issues, the repository must permit their issue submissions; a public repository is the straightforward choice.
3. Visit the repository's **Issues → New issue** page and confirm both forms appear. Submit one test issue for each category, or preview and discard before submitting.
4. Build and package native apps with the already configured repository, then click Help → Report a Bug / Request a Feature from an **installed** build.
5. Test with a non-maintainer GitHub account to ensure contributors have permission to open issues. GitHub requires testers to sign in to submit issues. For friends who don't want GitHub accounts, consider a separate optional web form later.

The issue forms do not automatically create GitHub labels, and do not require repository credentials/API tokens. These links open the default browser; GitHub handles authentication and submission.

**Privacy:** GitHub issues are visible to users who can access the repository and may be public. Instruct testers not to upload secrets, private artwork, sensitive file paths, or personal details. The diagnostics dialog is opt-in and nothing is automatically transmitted.

## Source setup and launch (existing GitHub workflow)

Upload all project files including hidden `.github/`, `assets/`, `tools/`, `tests/`, `feedback_support.py`, `main.py`, `requirements*.txt`, and `.gitignore` to your repository. Preserve directory structure.

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

Change the example paths to match your checkout. `requirements.txt` is unchanged.

## Run tests, build and package

Run in your project's virtual environment. Substitute `./.venv/bin/python` on macOS and `.\.venv\Scripts\python.exe` on Windows where needed.

```bash
python -m unittest discover -s tests -v
python tools/build.py --dry-run
python tools/build.py
python tools/check_build.py
python tools/package_release.py --dry-run
python tools/package_release.py
```

- Windows installer requires Inno Setup 6. Output: `releases/LinuxAnimationStudio-0.35.2-windows-setup.exe`.
- macOS uses `hdiutil`: `releases/LinuxAnimationStudio-0.35.2-macos.dmg`. Signing/notarization is not included.
- Linux produces `releases/LinuxAnimationStudio-0.35.2-linux.tar.gz`, a per-user installable archive with `install.sh` and `uninstall.sh`. It is not a `.deb` or AppImage.
- FFmpeg may still require the system installation or `LAS_FFMPEG_PATH`; installing LAS does not automatically install FFmpeg.

## Previous v0.33 feedback regression tests

1. GitHub Issues: Both issue forms appear on GitHub under Issues → New issue after the templates are on the default branch.
2. Form validation: Required reproduction/description fields work; optional diagnostic and screenshot fields remain optional.
3. Configured reports: On Windows, Linux, and macOS, Help → Report a Bug and Help → Request a Feature open the correct repository/template in the default browser.
4. Default destination: New source and installed builds point to `lafingputz/linux-animation-studio`; an explicitly unconfigured destination prompts for configuration instead of opening an invalid link.
5. Diagnostics: Help → Copy System Information displays meaningful version and platform data; contents appear on clipboard only when clicked. No artwork or sensitive paths included.
6. Settings persistence: A configured GitHub repository survives app restart; source and packaged installation behavior are correct.
7. Unit tests: Run the full suite, including the new dependency-free feedback tests and the Windows UTF-8 test fix.
8. Installer regression: Rebuild Windows setup, macOS DMG, and Linux tar.gz; check the configured issue URLs from installed apps.
9. Application regression: Drawing, pressure where supported, Color Studio, layers, animation, timeline, audio, export, workspaces, project save/load, and thumbnail cache still work.

## Verification status

Source compiles and the non-GUI suite is run in this environment. PySide6 is not available here, so visual GUI and platform packaging verification must be completed on your actual devices. This is a **test candidate**, not a claimed validated release. The Surface Pro 3's heavy 24 FPS animation playback limitation remains outside this feedback-focused release.

### v0.34.1 acceptance priorities

- Verify the toolbar bucket icon is visible in light/dark themes, and the cursor remains legible against dark, light, and colored artwork on all three OSes. Verify its hotspot fills the pixel actually indicated.
- Compare a full-canvas 1200×800 fill on the Surface Pro 3 against v0.34, including time until the UI responds. Run `tools/benchmark_fill.py`; that number excludes compositing and UI overhead.
- Rerun multi-frame fill opt-in tests and complete cross-platform draw/animation, save/load, and packaging regressions.
- Leave issue #2 open until the corrective release passes; reference/all-visible layer fills will be a future enhancement.
