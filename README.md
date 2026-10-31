# Linux Animation Studio v0.17.2 (Space/Pan Conflict Hotfix)

This patch builds on v0.17.1 and fixes the conflicting Space keyboard shortcut.

## Controls

- **Space + left-drag:** Pan the canvas without starting/stopping animation.
- **Middle-button drag:** Pan the canvas.
- **P:** Toggle animation playback.
- **Play/Pause button:** Toggle animation playback.
- **Ctrl+0:** Fit and center canvas.

The global Space playback shortcut has been removed because it intercepted the Space key required by canvas panning. The existing timeline visibility hotfix and v0.17 workspace improvements remain in place.

## Install

Update the four source files in your GitHub repository, then on the Surface:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

## Test

1. Zoom in, hold Space, drag the canvas, and verify playback does not toggle.
2. Press P and verify playback toggles.
3. Confirm the Play/Pause button and timeline still work.
4. With Wacom, test Space + pen drag to check whether Wayland tablet events are handled as mouse events.

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
