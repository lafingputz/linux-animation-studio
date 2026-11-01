# Linux Animation Studio v0.21.1

Targeted usability update based on v0.21.0; no changes to `.las` project format (remains v6).

## Improvements
- Frame thumbnails now have a **visible turquoise grip with three white lines** at their right edge. Drag this grip onto a later visible frame to extend its exposure. A hover tooltip and a short timeline hint explain the gesture.
- Adds **⏮ First** and **Last ⏭** buttons to the frame navigation row.
- Default customizable shortcuts: **`<` (Shift+comma)** for first frame, **`>` (Shift+period)** for last frame. Existing `,` and `.` previous/next shortcuts are preserved.
- Jumping to first/last frame pauses playback and follows existing `change_frame` audio seeking, onion-skin, and current-cel updates.
- Title bar and About show **v0.21.1**.

## Notes
- Exposure dragging extends only to a **visible later thumbnail**. For an exact destination frame or longer holds, use **Extend Hold To Frame…**.
- Extending holds does not silently overwrite an independent occupied cel.
- All existing v0.21 features, keyboard preferences, .las v1–v6 loading, audio embedding, Wacom pan, drawing tools, and exports are retained.
- The Qt GUI and Wacom interactions still require testing on the Surface Pro 3.

## Testing
1. Verify the turquoise grip appears on the **right edge** of thumbnails and is comfortably clickable.
2. Drag from frame 35 to 40; verify the hold extends to 40 and that undo/redo work.
3. Verify occupied cel protection.
4. Test `<`, `>`, `,`, `.`, including playback pause and audio seek.
5. Remap First/Last Frame shortcuts, restart, and verify persistence.
6. Verify compact timeline, Focus Mode, Wacom pan, audio and exports remain functional.

## Launch
```bash
cd ~/Projects/linux-animation-studio
source .venv/bin/activate
python main.py
```
