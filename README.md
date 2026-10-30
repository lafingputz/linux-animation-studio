# Linux Animation Studio v0.12 (experimental)

This update builds on the v0.11 source and retains `.las` v4 compatibility.

## Updates

- Toolbar Color button shows the chosen color (hex code and colored background).
- Brush and eraser previews now show an outlined nominal diameter (with pressure response while painting).
- Eraser remembers its own diameter independently of individual brush presets.
- Brush strokes retain frame-specific references in document-wide undo history, so undo/redo can switch to the frame of the affected stroke.
- Onion-skin compositing continues to preserve alpha. Newly imported image layers are labelled `[Reference]` and omitted from onion-skin ghost renders to avoid full-canvas image ghosts. To onion-skin imported artwork, copy it to an ordinary animated layer instead.
- Ctrl+Plus / Ctrl+Equals zoom in, Ctrl+Minus zoom out, Ctrl+0 resets zoom to 100%.

## Important limitations

- Frame insertion, frame deletion and track-mode conversion still reset the undo stack to avoid stale frame indexes. This is not yet a fully general document transaction history.
- Zoom starts at 100% and scales the drawing widget; scrollbars handle large zoom levels. Ctrl+0 resets to 100% (it is **not** automatic fit-to-window).
- On imported-image-heavy older projects, some non-reference layers may still ghost as a full image; use a static layer for reference backgrounds.
- Back up your `.las` projects before use. GUI, Wayland, and Wacom behavior have not been tested in this execution environment.

## Install / run

Upload `main.py`, `requirements.txt`, `README.md`, and `.gitignore` to the repository root on GitHub. Then on the Surface:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

No new dependencies.

## Suggested tests

1. Color swatch follows selected color.
2. Cursor outlines reflect actual brush and eraser diameter at different zoom levels.
3. Switching Eraser ⇄ Pencil restores two different sizes, including after using `[` and `]`.
4. Draw on frame 1, then frame 2, navigate to frame 3; Ctrl+Z should return to frame 2 and undo that stroke, and repeat to undo frame 1.
5. Use imported transparent and opaque images with onion skins on both sides; confirm no unwanted full-canvas tint.
6. Zoom using Ctrl+Plus, Ctrl+Minus, Ctrl+0 and verify stylus coordinates, selections, and PNG output are unchanged.
7. Regression-test `.las` saving/reopening, playback, frame navigation, and exports.
