# Linux Animation Studio v0.4

Native PySide6 sketching prototype for Pop!_OS 24.04 LTS and Wacom Intuos CTH-490.

## Run

```bash
cd ~/Projects/linux-animation-studio
source .venv/bin/activate
python main.py
```

No new dependencies beyond PySide6.

## Features

- Pressure-sensitive Wacom drawing (retained from v0.3)
- Cursor dot / size-aware eraser circle, including Wayland window-state refresh
- True transparent RGBA raster layers, drawn bottom-to-top
- Add, delete, rename, hide/show and reorder layers
- Erase transparency on selected visible layer
- Layer-aware stroke undo/redo, plus undoable layer edits and clear
- Save / reopen editable `.las` project (ZIP archive with PNG layers and manifest)
- Export composited, white-background PNG of visible layers
- Save shortcut `Ctrl+S`, Save As `Ctrl+Shift+S`, Open `Ctrl+O`
- Undo `Ctrl+Z`, Redo `Ctrl+Shift+Z` or `Ctrl+Y`; size `[` and `]`

## Important

- **Clear Layer** clears only the selected layer, not the full document.
- The white canvas is a display background; individual raster layers are transparent.
- Hidden layers are preserved in `.las` but omitted from exported PNG.
- `.las` files do not currently include undo history. Save before closing.
- The viewport is fixed at 1200x800 by default. No zoom, selections, animation, blend modes or layer opacity yet.
- History is limited to 50 actions / approximately 96 MiB; very large operations can exceed the budget as a single action.
- The drawing engine currently uses a full-layer snapshot **temporarily during each stroke** and stores cropped before/after patches in history. This is not yet an optimized tiled renderer.
- New/open prompts about discarding unsaved data; no autosave yet.
- This release has been syntax-tested and tested with offscreen Qt where available. Test actual tablet pressure and cursor behavior on your Surface.

## Suggested manual checks

1. Draw on Layer 1, add Layer 2, draw across it, then hide Layer 2.
2. Select Layer 2, erase a hole, and check the Layer 1 art appears beneath it.
3. Reorder and rename layers; undo and redo these actions.
4. Clear the selected layer then undo.
5. Save `.las`, close/restart the program, reopen it and verify all layers.
6. Export PNG and confirm hidden layers are excluded.
7. Test Wacom pressure and cursor handling after maximizing with the touchpad.

## GitHub workflow

On your main computer, unzip the release and upload `main.py`, `requirements.txt`, `.gitignore`, and `README.md` to the repository root. On your Surface:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```
