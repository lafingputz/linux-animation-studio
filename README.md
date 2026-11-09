# Linux Animation Studio v0.33.0

**Beta Feedback & GitHub Issue Reporting** (test candidate). Based on validated v0.32.0. LAS `.las` format **remains v6**; no modifications were made to rendering, brushes, timeline behavior, audio, or project serialization.

## New in v0.33

- GitHub **Bug report** and **Feature request** issue forms in `.github/ISSUE_TEMPLATE/`. Bug reports request the LAS version, operating system, steps to reproduce, expected/actual behavior, and optional screenshots/diagnostics. Feature requests ask which workflow needs improving and what the proposed solution should do.
- New **Help → Report a Bug…** and **Help → Request a Feature…** menu actions open the appropriate GitHub issue form in the user's default browser. No automatic issue creation or data uploads.
- New **Help → Copy System Information…** dialog displays LAS version, OS, architecture, Python, Qt, PySide6, and source/packaged status. Information is placed on the clipboard **only** when the user clicks the Copy button. No username, home directory, path to projects, IP address, artwork, or error logs are collected.
- New **Help → Configure Feedback Repository…** lets a tester or developer change the issue-tracker destination locally. The configured destination is stored in application preferences, not inside `.las` files. Feedback links accept canonical GitHub `owner/repo` identifiers only.
- The Windows test-suite UTF-8 decoding issue in `tests/test_distribution31.py` is corrected.
- Existing v0.32 thumbnail caching, dockable workspaces, Color Studio, frame tools, installers, and compatibility tests are preserved.

## Important: Set your REAL GitHub repository before distributing a beta

The source package deliberately **does not invent your repository URL**. Before building and sharing installers, open **`assets/feedback.json`** and set the repository identifier:

```json
{
  "repository": "YOUR_GITHUB_ACCOUNT/YOUR_REPOSITORY"
}
```

For example, use the `owner/repo` portion of your own GitHub repository's URL. Replace *both* placeholder words. The default is an empty string, meaning no public destination is preconfigured. **Do not distribute the app with an empty value if you expect one-click bug reporting.**

The `tools/build.py` PyInstaller helper already includes the full `assets/` folder in each native application build. **Rebuild the application and its installer after editing the JSON file.** If you change the JSON only in the source repository, already-built installations will not update their bundled copy. If an individual machine has a repository set in **Help → Configure Feedback Repository…**, that saved local override takes precedence.

If the maintainer doesn't set a repository, LAS prompts users to configure a destination rather than opening a guessed site. The GitHub issue URLs are:

- `https://github.com/OWNER/REPO/issues/new?template=01_bug_report.yml`
- `https://github.com/OWNER/REPO/issues/new?template=02_feature_request.yml`

### GitHub setup

1. Commit **the entire `.github/ISSUE_TEMPLATE/` directory**, including both `.yml` forms and `config.yml`, to your repository's **default branch**. Some GitHub upload interfaces hide dot-folders, so check carefully.
2. In GitHub repository **Settings → General → Features**, ensure **Issues** is enabled. For ordinary outside beta testers to create issues, the repository must permit their issue submissions; a public repository is the straightforward choice.
3. Visit the repository's **Issues → New issue** page and confirm both forms appear. Submit one test issue for each category, or preview and discard before submitting.
4. Edit `assets/feedback.json` with the actual `owner/repo`, build and package native apps, then click Help → Report a Bug / Request a Feature from an **installed** build.
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

- Windows installer requires Inno Setup 6. Output: `releases/LinuxAnimationStudio-0.33.0-windows-setup.exe`.
- macOS uses `hdiutil`: `releases/LinuxAnimationStudio-0.33.0-macos.dmg`. Signing/notarization is not included.
- Linux produces `releases/LinuxAnimationStudio-0.33.0-linux.tar.gz`, a per-user installable archive with `install.sh` and `uninstall.sh`. It is not a `.deb` or AppImage.
- FFmpeg may still require the system installation or `LAS_FFMPEG_PATH`; installing LAS does not automatically install FFmpeg.

## Acceptance tests for v0.33

1. GitHub Issues: Both issue forms appear on GitHub under Issues → New issue after the templates are on the default branch.
2. Form validation: Required reproduction/description fields work; optional diagnostic and screenshot fields remain optional.
3. Configured reports: On Windows, Linux, and macOS, Help → Report a Bug and Help → Request a Feature open the correct repository/template in the default browser.
4. Unconfigured reports: A blank `assets/feedback.json` prompts for configuration, rather than opening a broken/fabricated link.
5. Diagnostics: Help → Copy System Information displays meaningful version and platform data; contents appear on clipboard only when clicked. No artwork or sensitive paths included.
6. Settings persistence: A configured GitHub repository survives app restart; source and packaged installation behavior are correct.
7. Unit tests: Run the full suite, including the new dependency-free feedback tests and the Windows UTF-8 test fix.
8. Installer regression: Rebuild Windows setup, macOS DMG, and Linux tar.gz; check the configured issue URLs from installed apps.
9. Application regression: Drawing, pressure where supported, Color Studio, layers, animation, timeline, audio, export, workspaces, project save/load, and thumbnail cache still work.

## Verification status

Source compiles and the non-GUI suite is run in this environment. PySide6 is not available here, so visual GUI and platform packaging verification must be completed on your actual devices. This is a **test candidate**, not a claimed validated release. The Surface Pro 3's heavy 24 FPS animation playback limitation remains outside this feedback-focused release.
