# Linux Animation Studio v0.17.1 (Timeline Hotfix)

This hotfix is based on v0.17 and keeps the same v0.16-compatible drawing, brush, project and export features.

## Fix

- Restores the animation timeline that was invisible due to a zero-height layout allocation.
- Replaces the timeline area with a height-bounded, scrollable panel so controls remain reachable on the Surface Pro 3 without resizing the application beyond the screen.
- Synchronizes the timeline toggle label with visibility when a project opens or closes.
- No changes to `.las` format, brush libraries, or frame data.

## Install

Update `main.py`, `README.md`, `requirements.txt`, and `.gitignore` in your GitHub repository. On the Surface:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

## Test

1. Create or open a project: timeline frame thumbnails and FPS/onion controls should be visible.
2. Hide and show the timeline repeatedly: label should match state.
3. Scroll inside the timeline to reach controls and thumbnails.
4. Repeat maximized and verify the window never extends off-screen.
5. Verify drawing, Wacom pressure, onion skinning, saving, and animation export remain functional.

This build passes Python syntax compilation but has not been tested in a live Qt GUI on the Surface Pro 3.
