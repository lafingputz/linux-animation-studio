# Linux Animation Studio v0.3

Drop-in update for v0.2. Tested by syntax compilation; stylus/Wayland behavior needs checking on the Surface Pro 3.

## Updating via GitHub

On your main computer, unzip this archive and upload the **contents** (`main.py`, `requirements.txt`, `.gitignore`, `README.md`) into the **root** of your existing `linux-animation-studio` repository. Do not upload the enclosing v0.3 folder, `.venv`, or caches. Commit changes to `main`.

On the Surface:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

Dependencies are unchanged from v0.2.

## New

- Undo (`Ctrl+Z`) and redo (`Ctrl+Shift+Z` or `Ctrl+Y`) buttons and shortcuts.
- Each pen/mouse stroke is a single undo action; Clear is undoable.
- History stores cropped image patches for strokes, rather than a full-canvas snapshot per stroke. A single full-canvas temporary copy exists while a stroke is in progress. History is capped at 50 undo actions / approximately 96 MiB (except an individual large operation).
- `[` / `]` adjust brush size by one pixel.
- `Ctrl+S` opens the existing PNG export dialog. **This is not yet native project saving.**
- Restores the blank OS pointer on canvas entry, pointer updates, and window-state changes. Cursor bug fix is provisional until tested on Pop!_OS Wayland.

## Testing

1. Make three separate strokes. Undo three times and redo three times.
2. Undo one stroke, draw a new stroke: redo must no longer restore the old stroke.
3. Clear, undo, redo.
4. Draw using pressure and hover the stylus over the canvas, then maximize with your touchpad and return to canvas. The arrow should disappear.
5. Change size using `[` and `]`; check the eraser circle follows the new size.
6. Export PNG and confirm the custom cursor is not exported.

Known limitations: White-paint eraser (not real transparency); no layers, project file, or animation yet. While a stroke is active, undo/redo are ignored. A long stroke may redraw a relatively large region; more sophisticated tiles come later.
