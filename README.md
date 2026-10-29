# Linux Animation Studio v0.5

Python / PySide6 painting prototype for Pop!_OS 24.04 and a Wacom Intuos CTH-490.

## Update from v0.4

On your Mac, unpack this archive and upload `main.py`, `requirements.txt`, `.gitignore`, and `README.md` to the root of your existing GitHub repository. On the Surface:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

No new Python dependencies. Keep backups of important `.las` documents before testing a new build.

## New tools

- **Tool selector**: Brush, Select Rectangle, Move Pixels. Brush keeps pressure sensitivity and real transparency eraser from v0.4.
- **Select Rectangle**: drag to select; Ctrl+A selects the whole canvas, Ctrl+D deselects. Brush and eraser are clipped to the active selection.
- **Move Pixels**: drag the currently selected region within the active layer, or move all pixels on that layer if nothing is selected. Releasing commits one undoable move. Content moving beyond the canvas boundary is clipped.
- **Opacity**: click a layer, then adjust the right-hand slider from 0% to 100%; changes are undoable. A committed slider change creates one history entry, rather than one per slider motion.
- **Save/load**: projects still use v0.4's version-1 `.las` layout; the optional `opacity` field defaults to 100% when opening older projects.
- Existing Wacom, cursor, clear, layers, PNG, undo/redo, and shortcuts remain.

## Limitations of v0.5

- Rectangular selections only. Selection boundaries are not yet saved in `.las` files.
- Moves rasterize and commit to the active layer. Scaling, rotation handles, nondestructive transforms, and animation keyframes are **not included yet**.
- Moving an entire layer may use substantial memory for its undo snapshot, and large canvases remain CPU-rendered.
- As before, the PNG exporter writes a white background.

## Suggested QA

1. Open a v0.4 `.las`, verify its layers, save as a new filename, and reopen.
2. Draw in a rectangular selection: confirm brush and eraser do not affect outside pixels.
3. Select a portion of a layer, move it, and verify the source is transparent and other layers unchanged.
4. Undo and redo the move; move all layer pixels without a selection.
5. Change layer opacity, undo and redo it; save and reopen to verify opacity.
6. Try Wacom pen pressure, cursor hover, touchpad maximization, and PNG export.
7. Confirm you can still rename/reorder/hide/delete layers and undo those actions.

## Long-term brush roadmap

Multiple brush presets and importing a clipped image as a stamp/brush tip are planned future features; **not implemented in this version**. For clean future integration we'll separate brush presets from the document-layer system.
