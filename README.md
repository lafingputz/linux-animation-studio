# Linux Animation Studio v0.18 — Lasso Selection Test Build

This update builds directly from the tested v0.17.6 navigation release. It adds three modes under the existing **Selection** tool: Rectangle, Freehand Lasso, and Polygonal Lasso. Selection boundaries use an antialiased document-size ARGB mask and a QPainterPath; a bounding box is retained for move and transform handles.

## Controls

- **Rectangle**: press, drag, release.
- **Freehand Lasso**: drag to trace, then lift pen to close. The closing segment is drawn from pen-up to the first point.
- **Polygonal Lasso**: press/tap to set vertices. Finish by double-clicking/double-tapping, tapping near the first point (three or more points), or pressing Enter. Backspace removes a vertex, Escape cancels an unfinished polygon.
- **Ctrl+D**: deselect. **Ctrl+A**: select all.
- Choose **Move Pixels** or **Transform** to edit a selected region. **Brush from Selection** respects the mask.
- The dedicated **Pan Canvas** tool and **Space + Wacom drag** remain available.

## Important notes

- Selections are in-memory editing state and are not persisted in `.las` files; all raster edits made with them are saved normally.
- Existing `.las` v4 project files and the persisted custom brush library remain unchanged.
- Polygonal double-tap is supported with a short tap window, but the platform may also deliver an ordinary Qt double-click.
- Antialiased path clipping is supplied through Qt's painter; inspect stroke and eraser edges closely on the Surface.
- This is a **test build**. Python syntax compilation has passed; graphical application behavior, Wacom tablet behavior on Wayland, selection blending, and exporting must be verified on hardware.

## Acceptance tests

1. Rectangle selection: drag, paint, erase, move, and transform as before.
2. Freehand selection: trace a complex curve using Wacom; lift pen and inspect the closure.
3. Polygonal selection: test double-tap, closing near the start, Enter, Backspace, and Escape.
4. Paint and erase both near the edges and outside an irregular selected area.
5. Move only selected pixels, retaining the source artwork outside the selection.
6. Scale and rotate irregular selections. Verify no rectangular pixels are included.
7. Create both full-color and tintable brushes from lasso artwork.
8. Verify selections under Ctrl+0, zoom, panning, and Wacom hover alignment.
9. Regression: timeline, onion skins, layers, `.las` save/reopen, animation playback, PNG and MP4 exports, custom-brush dynamics, undo/redo.
10. Navigation regression: uninterrupted Space + Wacom dragging and dedicated Pan Canvas tool.

## Install using GitHub

Copy **main.py**, **README.md**, **requirements.txt** and **.gitignore** into your existing repository on the Mac, then run on your Surface:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```
