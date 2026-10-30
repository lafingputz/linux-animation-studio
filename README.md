# Linux Animation Studio v0.15

Native PySide6 drawing and animation prototype for Linux. Based on the tested v0.14.1 source.

## Changes

- **Brush from Selection**: choose an active raster layer, create a rectangular selection around visible pixels, then click `Brush from Selection`.
- **Brush from Active Layer**: create a brush tip from visible pixels of the selected active layer (including a layer imported with Ctrl+I). Transparent padding is trimmed.
- Give the new brush a name, then choose **Preserve original colors** (colored stamp) or **Use selected drawing color** (tintable alpha-mask stamp).
- The **Custom brush** dropdown switches between saved presets. The built-in brush dropdown is still available.
- **Stamp spacing** is a percent of the nominal brush diameter. Lower values create denser strokes; higher values create separated stamps.
- Use the normal Brush size and Brush opacity fields for a custom brush. Tablet pressure scales stamp size.
- **Delete Custom Brush** removes the saved brush preset, never pixels painted with it.

## Storage

Custom brush definitions live outside `.las` documents at:

`~/.local/share/linux-animation-studio/brushes/`

(or `$XDG_DATA_HOME/linux-animation-studio/brushes/` if that variable is set).

Each saved brush is a UUID-named `.png` for its tip and a matching `.json` for its properties. Keep this directory when migrating to another machine. The `.las` format remains version 4; artwork made using custom brushes is stored as normal raster pixels and does not require the brush preset to remain installed.

## Install / update

Upload `main.py`, `README.md`, `requirements.txt`, and `.gitignore` to the **root** of your existing GitHub repository. On Pop!_OS:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

No new dependencies beyond PySide6. The original FFmpeg package is still used for video export.

## Test checklist

1. Draw on a raster layer, rectangle-select an area, click Brush from Selection, and use the new preset.
2. Import a transparent PNG with Ctrl+I, select its raster layer, and create a brush from the layer.
3. Paint with a color-preserving stamp; ensure the source colors survive.
4. Create a tintable stamp; change the selected color and verify the new strokes adopt it.
5. Change custom-brush diameter, opacity, and spacing. Test continuous and widely spaced stamps.
6. Test Wacom pressure response and cursor size.
7. Close/reopen the program and verify the saved preset remains in the custom brush dropdown.
8. Delete a custom brush and confirm previously painted artwork remains intact.
9. Draw custom brush strokes on different frames and test cross-frame undo/redo.
10. Save/reopen a `.las` project, then render PNG/MP4 and verify custom-brush artwork appears.
11. Regression-check v0.14.1 raster/motion transforms, frame history, onion skins, and project management.

## Limitations

- Brush tip creation captures **the currently selected raster layer only**, not a composite of all visible layers. Use a temporary merged layer if needed.
- Brush tips are downscaled to a maximum of 512 pixels in either dimension for responsiveness on the Surface Pro 3.
- Stamps maintain their source orientation. Rotation, randomness, scattering and other advanced dynamics are planned for later releases.
- Spacing is in percent of the maximum configured brush diameter; pressure changes stamp size but not inter-stamp spacing.
- Raster strokes made with a custom brush are editable and undoable as raster content, not as separate procedural objects.
- This build was syntax-checked but not GUI-/tablet-tested in this environment. Please keep a v0.14.1 tag and back up important `.las` projects before upgrading.
