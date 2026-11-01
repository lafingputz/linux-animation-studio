# Linux Animation Studio v0.19 — Timeline Cels & Exposure Test Build

This source is based on **v0.18**. It retains the existing lasso modes, Wacom navigation controller, custom brushes, layers, transforms, motion objects, onion skins, and export tools.

## New timeline controls

- **Extend Hold**: with an *animated* layer active, enter the desired total number of exposure frames (including the current frame) and click Extend Hold. Existing blank frames are linked to the active cel; extra frames are appended up to the 120-frame limit. **The operation refuses to overwrite an independent nonempty cel.**
- **Break / New Cel**: on the current frame, duplicate the pixels into an independent cel and break the link to previous exposures. This is useful when changing a pose or expression.
- **Link From…**: on the current frame, enter any source frame number on the same layer. Reuses the editable source cel in the current frame. **This replaces the current frame's cel**, so save your work or choose an empty frame first.
- **Unlink**: detach the currently linked cel while retaining its pixels.
- **Go to**: jump directly to a numbered frame.
- **Track strip**: ◆ first/key cel, ━ adjacent hold, ↗ noncontiguous link, · empty cel, ═ static layer. Brackets identify the active frame. The original frame thumbnail strip remains.

The frame insertion, duplication and deletion controls remain. Undo and redo cover hold, break, link and unlink. Cels share one editable `QImage` instance in memory. Changing any linked instance updates its peers.

## Project format and backwards compatibility

- `.las` project **version 5** adds a `cel_id` per saved frame/layer entry. Existing `.las` versions **1, 2, 3, and 4** are still loadable as independent animated cels, and can then be saved in v5 format.
- Shared identities are reconstructed when opening v5 projects; the archive still saves frame-specific PNG assets for easy interoperability.
- **Back up your original `.las` files** before resaving them, since an older application may not support v5 projects.
- Selections remain temporary editor state, as in v0.18.

## Acceptance tests on Surface Pro 3

1. Draw on an animated layer, add blank frames, and extend a hold. Draw/edit a held frame and verify linked exposure frames update.
2. Try extending a hold into an occupied independent frame. It must refuse without erasing artwork.
3. Break a held cel, edit it, and verify earlier exposures are unaffected.
4. Link a cel from an earlier frame to a later noncontiguous frame, then draw in either and verify shared edits.
5. Unlink and verify subsequent edits are independent.
6. Verify the track strip represents key cels, holds, noncontiguous links, empty cels, and static layers.
7. Insert, duplicate, delete, jump between frames, and undo/redo timeline edits.
8. Verify onion skins, playback, PNG sequence, and MP4 export reproduce the expected exposure frames.
9. Open an old v4 `.las` project, verify existing independent cels are preserved, then save/reopen as v5.
10. Regression: Wacom Space+drag and Pan Canvas, three lasso modes, brush dynamics, transformations, timeline visibility, and custom brushes.

**Build verification:** Python syntax and ZIP contents can be checked without PySide6. Live Qt and Wacom behavior need acceptance testing on the Surface. This is a test build, not a certified stable release.

## Installation through GitHub

Copy `main.py`, `README.md`, `requirements.txt`, and `.gitignore` into your existing repository using your Mac. Commit the changes; on the Surface:

```bash
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```
