# Linux Animation Studio v0.17.4

Targeted follow-up to v0.17.3 for intermittent Wacom Space+drag canvas panning on Pop!_OS/Wayland.

## Changes
- Avoid resetting an active pan when Qt emits both tablet and synthesized mouse press events.
- Track movement from either event stream during a pan to accommodate Wayland input switching.
- Ignore synthesized mouse release during a tablet-owned pan to avoid stopping early.
- Preserve Space key focus protection, `P` playback, ordinary pressure-sensitive drawing, scrollable panels, timeline and onion skin improvements, existing `.las` projects, and exports.

## Installation
Replace the same four repository files, commit, then on the Surface:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

## Testing
1. Zoom in **until the canvas is larger than the visible viewport**, so there is space to pan.
2. Hold Space and drag continuously with the Wacom, several times, in different directions.
3. Confirm no painted marks, and that the canvas keeps moving until pen-up.
4. Release Space, confirm pressure drawing is normal, press P to play/pause, and check buttons do not reactivate with Space.
5. Confirm canvas alignment, timeline, onion skins, undo/redo and project saving.

Middle-mouse testing is optional if no mouse is connected. Python syntax compilation is checked; the Wacom/Wayland behavior still needs live testing.
