# Linux Animation Studio v0.16

Custom brush dynamics release, built as a drop-in replacement for tested v0.15.

## New for v0.16

Custom image-tip brushes now support:
- **Rotate along stroke:** align each stamp with pen travel direction.
- **Random rotation:** adjustable range ±0–180 degrees per stamp.
- **Scatter:** randomized horizontal/vertical offsets up to a percentage of nominal brush diameter.
- **Pressure-to-size strength:** 0% uses constant diameter; 100% maps light-to-heavy pen pressure into smaller-to-larger stamps.
- **Pressure-to-opacity strength:** 0% ignores pressure for opacity; 100% fades light strokes progressively.
- **Brush preview:** a small deterministic preview of the chosen custom brush and its dynamics.

All settings persist in `~/.local/share/linux-animation-studio/brushes/*.json` and are loaded on restart. Older v0.15 brush files automatically get safe defaults. Full-color and tintable stamp modes continue to work.

## Installation

On your Mac, extract the ZIP and upload `main.py`, `README.md`, `requirements.txt`, `.gitignore` into the **root** of the existing GitHub repository. On your Surface:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

No new Python libraries are needed. For MP4 export, FFmpeg must remain installed.

## Important behavior

These controls apply to **custom image brushes**. The four built-in presets remain unchanged. `Brush preview` is a compact static example refreshed when brush settings change, not an animated preview following the cursor.

Pressure and scatter are sampled per stamp. Extremely high scatter or dense spacing may affect responsiveness on older hardware; test at moderate values first. The undo subsystem records each stroke as a single operation. `.las` file format remains v4.

## Suggested acceptance tests

1. Create a brush from a selection and use it to paint.
2. Turn **Rotate along stroke** on and draw an S-shaped curve. Stamp orientation should follow the stroke.
3. Set random rotation to 0, then 90 degrees and compare results.
4. Set scatter to 0, then 50%, and compare stamp placements.
5. Test pressure-to-size at 0% and 100% with the Wacom.
6. Test pressure-to-opacity at 0% and 100% with a tintable brush.
7. Verify changing advanced controls updates the preview.
8. Restart the app and confirm controls persist.
9. Undo and redo custom strokes across frames; save/reopen and export `.las`/PNG/MP4.
10. Check v0.15 drawing, layers, animation, transform and imported-image onion skin functionality.

## Next proposed release

**v0.17: Selection modes**, including Freehand Lasso (close on pen release) and Polygonal Lasso (point-by-point, double-click/return-to-start to close). The selection-mask upgrade will require careful testing across paint, erase, transforms and custom brush creation.
