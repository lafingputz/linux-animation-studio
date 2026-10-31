# Linux Animation Studio v0.17

Small-screen workspace and multi-frame onion-skin update, based on v0.16.

## What's changed

- Custom brush spacing now accepts **1–400%** (previous minimum: 5%). Very dense stamps may be slow on older CPUs.
- The left settings panel scrolls independently, preventing the brush preview and Delete Brush button from overlapping or pushing other controls out of reach.
- **Ctrl+0** now calculates a fit-to-viewport zoom and centers the canvas using the scroll area's alignment. **Ctrl+1** is not implemented yet.
- **Middle-button drag** pans a zoomed canvas; **Space+left-mouse drag** also pans. Pen-as-mouse panning can depend on Wacom/Wayland tablet event routing and should be tested on the actual device.
- Timeline show/hide now uses a height-constrained container so reopening it should not stretch the application window offscreen.
- Independent **Previous ghosts** and **Next ghosts** controls (0–6) allow multiple tinted onion skins with distance-dependent fading. Both are saved and restored in `.las` projects.
- Existing brushes, transforms, motion objects, persistent tracks, selection tools, Wacom pressure, playback, and export paths are retained.

## Install on the Surface

Upload `main.py`, `README.md`, `requirements.txt`, and `.gitignore` to the root of your GitHub repository, commit, then run:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

No additional dependencies are required. Keep a known-good v0.16 tag and back up important `.las` projects before testing.

## Acceptance tests

1. Set custom stamp spacing to 1%, 2%, 3%, and 4%. Try dense strokes at different sizes and watch for lag.
2. With timeline shown on the Surface Pro 3, scroll the left panel all the way to the brush preview and Delete Brush controls. Check that nothing overlaps.
3. Test Ctrl+0 on small and large documents with timeline open and closed. The document should fit and be centered.
4. Zoom in, pan with middle-button drag, and test Space+left-drag. Verify normal brush drawing resumes afterwards.
5. Draw and select at multiple zoom/pan offsets and verify pen-to-pixel alignment.
6. Repeatedly hide/show timeline while maximized. Window geometry should remain usable.
7. Set previous ghosts to 3 and next ghosts to 1, then swap counts; verify correct number and progressive fade.
8. Verify static layers do not appear as onion ghosts and transparent imported artwork preserves alpha.
9. Save/reopen `.las` and verify onion settings remain, including opening old projects with default 1/1 ghosts.
10. Regression-test existing custom brushes, raster transforms, frame history, motion keyframes, Wacom pressure, playback, PNG sequences, and MP4 export.

## Testing status

Python syntax compilation has been checked. The graphical interface, Wacom/Wayland panning, precise geometry, and performance **have not been verified** in this environment.

## Known caveats

- At very high brush sizes and 1% spacing, image stamping may produce significant CPU load.
- A fit zoom below 25% is clamped by the existing zoom limit, so unusually large documents might not fit entirely yet.
- The timeline reflow and Space+drag behavior require on-device confirmation; if the window still moves offscreen or pen input conflicts with panning, report the exact conditions so the next patch can target them.
