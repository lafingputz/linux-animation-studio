# Linux Animation Studio v0.11

Drop-in replacement for v0.10. Requires Python 3 and PySide6. No new dependencies.

## Changes
- Onion-skin previews exclude static layers and appear above static backgrounds. Neighboring motion objects are included.
- Brush presets: Round, Pencil (light translucent strokes), Ink (crisp narrow strokes), Airbrush (soft alpha stamps).
- Brush size and opacity are remembered for each preset during the running session. Brush preset settings are application-session values, not yet persistent across restarts.
- File > Import Image as Layer (Ctrl+I): PNG, JPEG, WebP. Imported images are centered in a new animated raster track, and import can be undone/redone. Oversized images can be scaled to fit or cropped.
- Existing `.las` version 4 format and Wacom tablet handling retained.

## Run
```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

## Known limitations
- Airbrush and pencil are lightweight approximations, not advanced natural-media engines.
- Presets are not saved between application sessions yet.
- Imported images become animated tracks: drawings appear only in the current frame until you change track behavior to Static (which shares the image across frames).
- No interactive image placement transform yet.
- Onion ghosts are drawn over current artwork for visibility; future versions can offer a behind-current-art option.

## Test
1. Opaque static background + animated poses: check red/green ghost outlines at 20/50/100%.
2. Cycle all four brushes, change pressure, sizes and brush opacities, ensure brush tools, eraser and undo work.
3. Import transparent PNG and opaque JPEG/WebP; undo, redo, save and reopen.
4. Confirm existing `.las` projects, static/animated tracks, keyframes and PNG/MP4 export.
