# Linux Animation Studio v0.13

Focused stability update based on **v0.12**. The four repository-root files are `main.py`, `requirements.txt`, `.gitignore`, and this README.

## New in this version

- Frame creation, duplication, and deletion are now included in the existing document undo/redo stack. Deleted frames retain their animation cels and their position, and motion-object keyframe indices are restored when these operations are undone. Undo operates in chronological order: undo strokes made after creating a frame before undoing the frame creation itself. Standard shortcuts remain Ctrl+Z and Ctrl+Shift+Z / Ctrl+Y.
- Rectangle Select has a crosshair cursor and Move has a four-way arrow cursor. Brush and Eraser retain their size outlines.
- Imported image layers are no longer automatically excluded from onion skins. The ghost is tinted using `CompositionMode_SourceIn`, retaining the source's alpha silhouette. Static layers remain excluded. **Opaque JPEG backgrounds still produce an opaque rectangular ghost**: use a transparent PNG/WebP, remove the background, or place the source on a static track if a ghost is undesirable.

## Installation

On the Mac: upload these four files to the root of your existing GitHub repository, and commit as `v0.13 - Frame history, tool cursors, alpha-aware onion skins`.

On Pop!_OS:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

No new dependencies. `.las` stays project format v4. Back up important projects before testing.

## Tests to run on the Surface

1. Draw on Frame 1, create Frame 2, draw there, and create Frame 3. Undo drawing on Frame 2, then undo the creation of Frame 3, then Frame 2. Redo to recreate them in the correct order.
2. Duplicate a frame with artwork. Undo duplication and redo it; verify image contents and independent editable cels remain correct.
3. Delete an interior frame that contains multiple animated layers. Undo, verify the original frame position and artwork, then redo.
4. Create a motion object with keyframes on both sides of an inserted/deleted frame; verify undo/redo restores keyframe timing.
5. Hover the Wacom pen with Rectangle Select and Move selected; check the crosshair and four-way cursor. Maximize the window and retest.
6. Import transparent PNG/WebP art onto an animated layer; place art on two neighboring frames and check tinted onion skins respect transparent pixels. Also test an opaque JPEG and static layers.
7. Regression-test drawing, pressure, cross-frame undo, playback, MP4/PNG export, save/reopen and legacy `.las` files.

## Known limits

- Motion-object creation and track-mode conversion still clear history. Keyframe edits are not undoable yet.
- History is memory-capped; very large frame deletions may evict older undo steps.
- This build has passed Python source compilation, not actual GUI/Wacom testing in the target Pop!_OS environment.
