# Linux Animation Studio v0.7

Pressure-sensitive drawing with editable layers, frame timeline, onion skinning and playback.

## Install/update

Upload `main.py`, `requirements.txt`, `README.md` and `.gitignore` to the repository root on GitHub. Then on Pop!_OS:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

## New controls

- **Onion skins:** check the box to view one preceding frame in red and one following frame in green. Adjust Ghost opacity 0–100%. Ghosts are overlay-only and never exported.
- **Playback:** Play/Pause button or Space (when the canvas owns focus); Stop returns to Frame 1. Check Loop to repeat the sequence. Playback FPS comes from the existing FPS input.
- **Frame navigation:** Alt+Left and Alt+Right.
- **Numeric field focus:** Enter commits values and returns focus to the canvas. Clicking/pressing the canvas (including pen press) restores shortcut focus. `[` / `]` still change brush diameter by 1 px.

## Notes

- Playback does not change the artwork or mark an otherwise saved project dirty. FPS, onion settings, and loop preference are stored in the v2 `.las` manifest, with defaults when loading older projects.
- v0.6 limitations remain: each frame owns a complete set of raster layers; switching frames clears undo history. Export PNG exports the currently selected frame only. Video export is planned for v0.8.
- Keep backups of important `.las` files.
- Dependencies unchanged (PySide6, Pillow, NumPy, pytest).
