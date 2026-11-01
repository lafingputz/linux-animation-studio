# Linux Animation Studio v0.22.0 (experimental)

Built on the validated v0.21.1 source. Desktop Python/PySide6 drawing and 2D animation app.

## New in v0.22

- **Multi-frame edit toggle:** In the **Cels** timeline tab, enable **Multi-frame Edit**. Select frames with Shift+click (range) or Ctrl+click (individual), then draw, erase, or apply a raster transform. The current active layer is the target; its selected frames are edited at the same document coordinates.
- **Shared cel safety:** Frames sharing a cel ID are edited only once per operation. Linked and held frames remain linked. To edit them independently, first use Unlink or Break / New Cel.
- **Grouped history:** An entire multi-frame stroke or raster transform is one undo/redo timeline snapshot. Large selections may consume noticeably more memory and time; this is a test build.
- **Live exposure drag preview:** Hold the turquoise handle at a frame's right edge and move toward later frames; destination frames are highlighted while dragging. Artwork changes only on release. Existing independent artwork remains protected.
- **Continuous waveform dragging:** Drag across the audio waveform to seek the playhead and corresponding frame continuously. **This is silent seeking**: audible snippet playback while scrubbing is not supported yet.
- Title and About information updated to v0.22.0.

## Installation

Keep the standard four files in your GitHub repository, pull on the Surface, and run:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

Requires Python and PySide6, plus FFmpeg for audio handling and MP4 output. No change to `requirements.txt`.

## Compatibility and safety

- `.las` project format remains v6 and older project loading code is retained.
- Back up important `.las` files before the first multi-frame edits. This build hasn't been run against an actual Wacom/Qt GUI here.
- Multi-frame edits affect the active *animated raster layer*, not every layer or motion object. Motion-object keyframes are not batch transformed.
- Existing selection masks apply at the same document-space coordinates to each target cel.
- All selected frames can be shared cel exposures; they will be processed once per unique cel.
- The timeline's maximum frame count and existing export behavior remain unchanged.

## Suggested acceptance tests

1. Select frames 2–5 with Shift+click, enable Multi-frame Edit, and paint a stroke. Check all selected **independent** cels.
2. Undo once and verify every target frame reverts; redo once and check all return.
3. Repeat with eraser, custom brush, pressure-sensitive Wacom, and lasso selection.
4. Link two selected frames to a shared cel, draw with multi-edit, and verify no doubled opacity or repeated marks.
5. Transform several independent selected cels and undo once.
6. Toggle Multi-frame Edit off and confirm edits once again affect only the current cel.
7. Drag an exposure grip and confirm frames highlight before releasing; confirm occupied-frame protection.
8. Drag the waveform and confirm the playhead updates as you move, then audio plays from the sought position.
9. Confirm v0.21.1 regression behavior: Space+Wacom pan, Focus Mode, playback, onion skins, existing linked/held cels, save/reopen, PNG and MP4 export, keyboard preferences, shortcuts.

Please report failures as **passed / partial / failed / untested** and note any errors shown in the terminal.
