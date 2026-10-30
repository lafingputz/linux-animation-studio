# Linux Animation Studio v0.14.1 (transform cursor hotfix)

Based on v0.13, adding an on-canvas Transform tool while preserving the existing drawing, animation and export systems.

## Install

Upload `main.py`, `requirements.txt`, `.gitignore` and `README.md` to your existing GitHub repository. On Pop!_OS:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

## Raster transform

1. Save a backup of your `.las` project first.
2. Select a raster layer; optionally make a rectangular selection.
3. Choose **Transform** on the left toolbar.
4. Drag inside the transform box to move; drag a corner to scale proportionally; drag the circular handle beyond the top edge to rotate. The center marker moves the transform pivot.
5. Click **Apply Transform** or press Enter while the canvas has focus. Click **Cancel Transform** or press Esc to abandon the preview.
6. Ctrl+Z / Ctrl+Shift+Z undo/redo the finished raster transform.

The first version uses **uniform scaling** on all corners, and the canvas-aligned source rectangle is the full layer unless you select a region. Edges outside the canvas are clipped. Each transform is applied to the original pixels only once, on confirmation. Undo stores a full-canvas patch for transforms, which may be memory-intensive for large canvases. Transformation of static layers updates their shared artwork.

## Motion object transform

Select a motion object from the timeline dropdown, then click **Transform Motion Object** on the left. Drag to move, a corner to change scale, or the rotation handle. Apply writes an undoable keyframe at the current frame; Cancel discards the preview. The motion object's transform retains the existing canvas-center pivot: the center handle is a visual-only adjustment during this prototype, and its position is not persisted. For precise values, use the existing X/Y/Scale/Angle fields.

Keyframe values and raster pixels are stored in the existing `.las` version 4 format. v0.13 and older project files continue to be readable. This version does not add new dependencies.

## Test on your Surface Pro 3

- Wacom hover and pressure still draw normally in Brush mode.
- Select a small area, transform it, cancel, retry and commit; inspect untouched areas.
- Undo/redo a raster transform, including after switching frames.
- Transform a motion object at frame 1 and frame 12, check playback and MP4 export.
- Save and reopen `.las`, including an older project.
- Verify that changing frames automatically cancels an unfinished transform.

**QA limitation:** Syntax checked, but not GUI/Wacom-tested in this environment. Back up important artwork; report any unexpected behavior before replacing the tagged v0.13 stable release.

## v0.14.1 cursor hotfix

The Transform tool now uses the OS arrow instead of an invisible cursor, including when transforming motion objects. Brush/eraser and selection/move cursors are unchanged. This is a UI-only patch; project format and dependencies are unchanged.
