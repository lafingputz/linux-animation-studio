# Linux Animation Studio v0.27.1

**Color Studio palette refresh fix and individual swatch removal.** This is a focused maintenance release based directly on v0.27.0. Drawing/Animation workspaces, drawing engine, audio, exports, and `.las` project format are unchanged.

## Changes

- **Fixed: My Palette appears empty when first opening the Palettes tab.** The swatch grid is populated when Color Studio initializes and refreshed whenever you switch back to the Palettes tab, even if the palette dropdown selection has not changed.
- **Remove individual palette swatches.** Click a color swatch, then use **Remove selected**, or **right-click** the swatch and choose **Remove color from palette**. The visible button also supports pen/tablet users without a convenient secondary-click gesture.
- The removal control is disabled until a swatch is selected. The selected swatch gets a blue border, and switching palettes clears that selection.
- A swatch removal saves immediately to Color Studio's `QSettings` preferences and does **not** change the active brush color or delete the palette itself. Swatches can be added again using **Add current color**.
- Existing named palettes and color data are preserved. No `.las` document format update; version **6** remains in use.

## Acceptance checklist

1. Create/open a project and set a brush color.
2. Open **Color Studio → Palettes** for the **first** time. If My Palette already has colors, verify that they appear without switching the dropdown.
3. Add a new color to My Palette. Verify that it appears immediately.
4. Switch to **Disc**, then back to **Palettes**. Verify that the swatches remain visible.
5. Switch to **Starter**, then back to **My Palette**. Verify that each palette shows its own colors.
6. Click a swatch. Verify that it gets a blue border and becomes the chosen drawing color.
7. Click **Remove selected**. Verify that only the selected swatch disappears and the chosen drawing color stays the same.
8. Right-click a different swatch and select **Remove color from palette**. Verify that it is removed.
9. Restart LAS and reopen Color Studio. Verify removed colors remain removed and remaining colors still appear instantly.
10. Check that the Palettes tab fits on the Surface Pro 3, including the pen-accessible **Remove selected** button.
11. Verify no regression in Color Disc/Harmony/Values, Drawing/Animation workspace switching, `.las` saving/loading, brushes, animation, audio, or export.
12. Where possible, repeat startup, palette, and persistence checks on Linux, Windows, and macOS.

**Testing status:** Python source compilation and archive integrity checks are performed before release. GUI interactions must be validated on target hardware; this is a testing candidate. Back up important projects before testing development builds.

## Setup and launch

Replace the corresponding four source files in your GitHub repository, commit, and pull on each device. The `.venv` is not included.

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

Use the actual repository paths on Windows and macOS. Python 3.12 with PySide6 is required. MP4 exporting requires FFmpeg (PATH or `LAS_FFMPEG_PATH`). macOS pen-tablet input remains unverified due to unsupported older Wacom driver/hardware.
