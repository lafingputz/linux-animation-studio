# Linux Animation Studio v0.10

Persistent animation layer tracks and frame-step shortcuts. Tested with Python syntax compilation; GUI/tablet functionality requires testing on your Surface Pro 3.

## Update via GitHub

Upload `main.py`, `README.md`, `requirements.txt`, and `.gitignore` to the **root** of your existing repository. On the Surface:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

No new dependencies.

## What's new

- A layer now exists across **all frames**. Name, visibility, opacity, ordering, and layer identity remain consistent while changing frames.
- The **Track behavior** control in the right-hand Layers panel offers:
  - **Animated:** the same track remains selected, but each frame has its own editable cel. A blank frame receives transparent cels; duplicating a frame copies the cels.
  - **Static:** the artwork is shared across all frames. Edits to it show everywhere, ideal for backgrounds.
- `,` previous frame and `.` next frame, in addition to Alt+Left and Alt+Right. Shortcuts should be used while working in the canvas, not while entering numbers.
- `.las` version 4 supports this model. The loader migrates v0.4 through v0.9 documents by preserving each unique legacy layer ID as a track, using transparent cels where that track was absent. Older saves remain untouched until you save over them.

## Caveats

- **Back up projects** before upgrading. Version 4 files are not readable in older releases.
- Switching an **animated** layer to **static** replaces all its frame-specific cels with the current frame's artwork, after a confirmation dialog. Save As a different filename first if the drawings matter. Switching a static layer to animated creates independent cels containing the current artwork.
- Converting layer mode is **not undoable** in this version. Layer operations and stroke undo/redo are supported, but undo history clears when switching frames, as before.
- The source is still mostly in `main.py`; later refactoring into modules is recommended.
- Static artwork currently gets repeated in the ZIP archive for compatibility and simplicity. A later release can deduplicate it on disk.

## Suggested acceptance tests

1. Create three blank frames, draw on a layer in frame 1, move to frame 2, verify same named layer exists and is selected but its cel is blank.
2. Draw unique art in frames 2 and 3, move with comma and period, verify each cel is independent.
3. Add, rename, hide/show, reorder and delete tracks. Check consistency throughout all frames and undo/redo where supported.
4. Make a new background layer static. Paint on one frame, verify it appears on all frames, including after adding a blank frame.
5. Duplicate a frame: animated cels should be copies and static cels should stay shared.
6. Save/reopen the version 4 `.las` file. Confirm layer modes, art, frame count and motion objects.
7. Load a v0.9 `.las` animation with differently named layers on different frames; verify no artwork disappears and missing cels are transparent.
8. Test onion skins, playback, PNG sequence, MP4 export, Wacom drawing and project management.
