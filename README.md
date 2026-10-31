# Linux Animation Studio v0.17.5

Targeted canvas-navigation candidate fix for a Wacom stylus pan that begins moving and then stops before the pen is lifted (Pop!_OS, Wayland).

## Changes from v0.17.4

- Observe the full duration of an active pan across application widgets: scrolling can move the canvas out from under the stylus, changing the event recipient.
- Prefer real tablet movement once it is detected; discard duplicate or stale synthetic mouse moves instead of letting them corrupt the tablet's previous position.
- Keep Space from activating focused buttons. Releasing Space or deactivating the application cancels a pan.
- Provide optional diagnostic output for event continuity and scrollbar movement.
- Retain v0.17.4 brush dynamics, timeline, onion skin ranges, save format, export, and existing drawing modes.

## Install

Replace the same four repository files in GitHub and run on the Surface:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

## Test

1. Zoom in to **200% or more**, so the document is larger than the viewport and both scrollbars have room to move.
2. Press and hold **Space**, touch the canvas with the pen, and drag continuously in several directions. The canvas should follow until pen-up.
3. Confirm there are no stray marks. Release Space and confirm drawing and pressure work normally.
4. Click a tool button and press Space; it must not reactivate. Press **P** to test animation playback.
5. Check timeline hide/show, onion skins, project reopen and export.

## If panning still stops: optional diagnostic log

Start the app in a terminal using:

```bash
LAS_PAN_DEBUG=1 python main.py 2>&1 | tee ~/las-pan-debug.log
```

Zoom in, perform one slow Space+Wacom drag that stalls, release the pen, and inspect the lines beginning `[LAS PAN]`. `MOVE` entries report how far Qt says the pen moved, the scrollbar values before/after, and the scroll limits. The distinction matters:

- `START` followed by no `MOVE`: the pen movement events stopped reaching the app.
- `MOVE` entries with delta `(0, 0)` or unchanging positions: Qt's reported global pen position is not advancing.
- `MOVE` entries with changing delta but fixed scrollbar values at a limit: the viewport cannot scroll farther in that direction.

Feel free to paste just the `[LAS PAN]` lines. The log prints pointer positions in display coordinates, so review them before sharing if you prefer. No middle mouse is needed to test.

Static Python syntax checks passed. Real tablet/Wayland behavior is not verified until tested on the Surface.
