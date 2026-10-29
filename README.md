# Linux Animation Studio v0.6

A Python/PySide6 drawing and early frame-by-frame animation prototype for Linux, tested by its developer on Pop!_OS 24.04 with a Wacom Intuos CTH-490 in earlier releases.

## New in v0.6

- Dedicated left-side Brush, Eraser, Rectangle Select, and Move Pixels tools.
- Numerical brush size in pixels (1–500), with `[` and `]` changing it one pixel.
- Numerical layer opacity (0–100%).
- Collapsible frame timeline. Add blank, duplicate, delete, and select frames.
- Frame thumbnails and frame navigation.
- Save animations in `.las` format version 2, and open version 1 files from v0.4/v0.5.
- Per-frame editable raster layers.

## Install/update

Upload `main.py`, `requirements.txt`, `README.md`, and `.gitignore` to the **root** of your GitHub repository. On your Surface:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

No additional dependencies are introduced over v0.5.

## Important v0.6 limitations

- The timeline is **editing-only**: playback and onion skins are planned for v0.7.
- Frames store independent copies of their layer content (duplicate frame copies the current pose). This is deliberately a small first step toward a full cel/track model.
- Undo/redo is **per frame**; switching frames resets history. Adding, duplicating and deleting frames are **not yet undoable**. Save a backup before major changes.
- Layer list structure is currently independent in each frame. A proper persistent layer-track architecture will come later.
- Brush and eraser use a shared size value for now. Selection, moving, opacity, Wacom drawing, PNG export and cursor handling are inherited from v0.5.
- `Ctrl+S` saves `.las` in version 2. Earlier builds cannot open v2 projects, so preserve a copy of existing v0.5 artwork.

## Keys

- `Ctrl+Z` Undo / `Ctrl+Shift+Z` or `Ctrl+Y` Redo
- `Ctrl+S` Save `.las`, `Ctrl+Shift+S` Save As, `Ctrl+O` Open
- `[` / `]` Brush diameter -/+ 1 px (except when numerical inputs are focused)
- `Ctrl+A` Select all / `Ctrl+D` Deselect

## Suggested tests

1. Open an existing v0.5 `.las` project and save a copy under a new name.
2. Draw using Wacom pressure, switch Brush and Eraser in the left panel.
3. Type `10` in brush size and test `[` and `]`.
4. Type `35` in opacity and verify the selected layer changes.
5. Add a blank frame, draw another pose, return to first frame.
6. Duplicate a frame, change the copy, verify the original remains unchanged.
7. Delete a frame and confirm the others survive.
8. Save/reopen `.las`, verify frame count and contents, opacity and frame selection.
9. Hide/show the timeline and test PNG export of the active frame.

## Notes

Source has been checked for Python syntax; interactive behavior requires testing on the target Pop!_OS machine.
