# Linux Animation Studio v0.17.3

This is a focused input fix built on v0.17.2.

## Fixes
- Space held while dragging on the canvas now pans using **direct Wacom tablet events** as well as mouse events.
- Space keypresses are intercepted while the main application window is active, so the last-focused Qt button is not triggered repeatedly.
- Middle mouse drag remains a pan shortcut.
- Playback is still assigned to **P** or the Play button.
- Release Space to return to drawing.
- Focus loss cancels Space and panning state.

## Installation
Replace the four repository files with those in the zip, commit and pull on the Surface:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

## Tests to run
1. Click Brush, Eraser, Play, and other UI buttons; press Space afterward. No button should reactivate.
2. Zoom in until both scrollbars have room to move. Hold Space and drag using the Wacom pen. No stroke should be created.
3. Release Space and draw normally; pressure should still work.
4. Test middle mouse drag, `P` playback, and Wacom alignment after panning.
5. Hide/show the timeline and verify it still stays onscreen.

Note: Source compilation checks pass, but this patch has not been interactively tested with your Surface, Wacom, or Wayland installation.
