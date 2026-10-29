# Linux Animation Studio v0.8

Drawing, layers, selections, Wacom pressure, frame timeline, onion skins, playback, and **animation export**. Built from v0.7.

## Update via GitHub

On your Mac, upload `main.py`, `requirements.txt`, `README.md`, and `.gitignore` to the repository root. Do **not** upload `__pycache__` or `.venv`.

On Pop!_OS:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
sudo apt update && sudo apt install -y ffmpeg
python main.py
```

The `ffmpeg` package is required only for MP4 export. All other Python requirements are unchanged.

## File menu / project lifecycle

- **Ctrl+N** New Project: choose canvas width and height.
- **Ctrl+O** Open existing `.las` project (supports v0.4–v0.7 files).
- **Ctrl+S** Save the editable project.
- **Ctrl+Shift+S** Save As.
- **Ctrl+W** Close Project: leaves the application open with a welcome screen.
- **Ctrl+Q** Quit.
- **Ctrl+E** Export Animation.
- Unsaved edits trigger **Save / Discard / Cancel** before closing, opening another project, or quitting. Canceling a Save As dialog keeps the current artwork open.

## Animation export

- File > Export opens an export dialog with PNG sequence (transparent or white background) and MP4 (H.264).
- Choose output FPS (1–60). Duration is preserved approximately by repeating/skipping source frames. A partial final frame may cause rounding by up to one output-frame duration.
- Export only composited visible layers; onion skins, selection boxes and pointer previews are not included.
- PNG sequences are written to an `animation_frames` subfolder of your chosen directory. **Back up existing PNG sequences:** existing numbered output files can be overwritten, and pre-existing surplus frames may remain.
- MP4 exports are H.264/yuv420p with selectable high, balanced, or small-file quality, using a white background for transparency. Odd canvas dimensions are padded by one pixel for encoder compatibility.
- Export is incremental: only the active rendered frame is held in memory while PNGs are prepared. The window may be less responsive during encoding on older hardware. Export cancellation terminates FFmpeg but partial PNG-sequence files are not automatically removed.
- Save `.las` before exporting important work; exports do not replace project files.

## Known limitations

- Each animation frame holds an independent set of layers, so large projects can use considerable memory.
- Undo history clears when changing frames. Adding/removing animation frames cannot be undone yet.
- Export has no audio. MP4 requires a working system FFmpeg with `libx264` available.
- This source passed syntax checks, but GUI behavior has not been tested on the Surface Pro 3 yet.
