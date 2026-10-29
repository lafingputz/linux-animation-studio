# Linux Animation Studio v0.9 (motion keyframes prototype)

Builds directly on v0.8. Traditional frame drawings, pen input, layers, playback, PNG and MP4 export remain.

## Install
On Mac, upload `main.py`, `README.md`, `requirements.txt`, `.gitignore` into the GitHub repository root. On Pop!_OS:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

## Motion-object workflow
1. Save a backup of your artwork. Create an animation with at least 12 frames (Duplicate or + Blank).
2. On the first frame, paint an object on its own layer. Select that layer.
3. Click **Make Motion Object from Layer** in the timeline. The pixels in that layer on the current frame are cleared and stored as independent reusable artwork. This is **not yet undoable**.
4. Select the motion object. At frame 1, use X/Y/Scale/Angle and **Set Keyframe**.
5. Move to frame 12, enter a different X value and **Set Keyframe**.
6. Play. X/Y, scale and rotation values interpolate linearly between keyframes. Preview, onion skins, PNG sequence, and MP4 include the motion object.
7. Save a `.las` project and reopen it to verify motion object and keyframes are retained.

The X/Y values represent relative offset in document pixels. A source image remains the original full-canvas image with transparency; rotation/scale occur around the canvas center, so small drawings far from the center may move unexpectedly. Place source artwork centrally for predictable rotation.

## Limitations
- Motion objects are rendered above all raster layers, and have no custom z-order controls yet.
- `Make Motion Object` clears the currently selected raster layer in the active frame. Save a copy first. Not undoable in this version.
- Keyframe changes are not undoable. Deleting the last keyframe is disallowed.
- Frame creation/deletion shifts keyframe indices; deleting a keyed frame removes its key.
- Motion-object transform editing uses numerical controls, not draggable bounding-box handles. Interactive visual transforms and proper object origin controls are deferred.
- Limit 20 motion objects and 120 frames; no reusable linked cels for raster drawings yet.
- `.las` format upgraded to version 3. v0.9 can open older v0.4–v0.8 documents, but older app versions cannot open files saved by v0.9.
- If you want to test FPS playback with a moving object, make enough frames first; objects only animate across existing frames.
