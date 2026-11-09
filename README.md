# Linux Animation Studio v0.33.1

**Beta Feedback & GitHub Issue Reporting** (test candidate). Based on validated v0.32.0. LAS `.las` format **remains v6**; no modifications were made to rendering, brushes, timeline behavior, audio, or project serialization.

## New in v0.33.1: Selection Clearing & Clear Layer

- **Delete** or **Backspace** clears only the selected pixels of the active raster cel. If nothing is selected, neither key erases artwork.
- **Edit → Clear Selected Pixels** provides a menu alternative.
- **Edit → Clear Active Cel / Layer** clears the entire current cel, regardless of selection. Static layers intentionally clear across all frames because their artwork is shared.
- Undo/redo handles clearing in one step and restores **all linked exposures** together.
- Multi-frame Edit operates on selected frames only when explicitly enabled. Repeated linked exposures are edited once.
- Rectangle and lasso selections preserve their clipping masks, including antialiased edges; edits invalidate timeline thumbnails.
- Both deletion shortcuts can be customized under **Edit → Keyboard Shortcuts**. Text inputs are protected from those shortcuts.
- The GitHub reporting destination remains `lafingputz/linux-animation-studio`. Project format is still `.las` v6.

### Quick verification for v0.33.1

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

- Windows installer requires Inno Setup 6. Output: `releases/LinuxAnimationStudio-0.33.1-windows-setup.exe`.
- macOS uses `hdiutil`: `releases/LinuxAnimationStudio-0.33.1-macos.dmg`. Signing/notarization is not included.
- Linux produces `releases/LinuxAnimationStudio-0.33.1-linux.tar.gz`, a per-user installable archive with `install.sh` and `uninstall.sh`. It is not a `.deb` or AppImage.
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
