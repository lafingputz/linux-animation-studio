# Linux Animation Studio v0.21.0 (test build)

Python/PySide6 frame-by-frame drawing and animation for Linux, retaining the v0.20 embedded audio, lasso, brush, Wacom pan, linked cel, exposure, and Canvas Focus features.

## Changes

- Central `APP_VERSION` constant and **Help > About** version information (fixes previous stale title).
- Timeline details organized into **Cels**, **Onion Skins**, **Audio**, and **Motion** tabs. Transport and frame thumbnails stay in the timeline view.
- **Extend Hold To Frame…** for exact endpoints; the rightmost 12 pixels of a frame thumbnail act as an exposure drag handle. Drag rightward to a later visible frame; stops safely rather than overwriting independent artwork. For endpoints beyond visible frames, use the exact-frame command (up to frame 120).
- **Shift+click** selects a range of frame thumbnails; **Ctrl+click** toggles individual frames. **Apply to Selected Frames…** in Cels tab can link selected empty frames to the playhead cel, unlink, or break into independent cels. Batch changes are a single undo step.
- **Edit > Keyboard Shortcuts…**: configurable non-file-menu commands with conflict checking, reserved Space for pen panning, restore defaults, and persistent `QSettings` preferences. File commands remain predefined in this version.
- `.las` format remains v6; existing projects should be preserved. Back up important files prior to testing.

## Run

From the existing repository on the Surface:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

Requirements: PySide6, and FFmpeg available on PATH for MP3 waveform extraction and MP4 exporting.

## Suggested acceptance checks

1. Window title and Help > About say v0.21.0.
2. Tabs make audio and cel controls accessible without hiding the timeline thumbnails.
3. Drag the right edge of frame 35's thumbnail to frame 40 (with that layer's intervening cels empty), then edit the source drawing.
4. Test Extend Hold To Frame with an exact target, an occupied frame, and undo/redo.
5. Shift-click and Ctrl-click thumbnail selections; batch link, unlink, and break operations. Test undo/redo and project save/reopen.
6. Remap `P` to another unused shortcut, test playback, restart, and confirm persistence; test conflict prevention and restore defaults.
7. Verify Tab focus mode, Space+Wacom pan, pressure drawing, lasso tools, audio import/playback/waveform, exposure cels, older `.las` files, and MP4 export.

## Known limits and caution

- This is an experimental test build. Python syntax was checked; live PySide6/Wayland/Wacom and audio behavior were not testable in the build environment.
- The frame strip provides an end-handle drag to later *visible* frames. Shortening existing exposures by dragging left and auto-scrolling during drag are not yet implemented.
- Batch cel operations work on the **active animated layer**; bulk painting/erasing/transforms are deferred.
- Shortcut customization covers canvas/timeline commands in the preferences dialog, not File-menu commands, native tablet gestures, or Space+drag. Drag recording and profile import/export are not included.
- Deep multi-module refactoring is deferred to a dedicated follow-up to limit regressions.
- Waveform is still click-to-seek, not continuous audible scrub.
