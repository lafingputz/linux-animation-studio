# Linux Animation Studio v0.20 (test build)

Based directly on v0.19. All existing drawing, Wacom navigation, lasso, brush, layers, exposure holds, linked cels, timeline, and export functionality is retained in the source.

## New

- A **single embedded WAV/MP3 track** in the animation timeline, including waveform overview, mute, volume, and a waveform-click frame seek control.
- Audio plays during animation playback, seeks when the selected animation frame changes, and restarts with looping animation.
- Imported audio is **embedded directly in `.las` version 6**, so the source audio file is not required after saving. Open v1–v5 projects as before; older LAS versions may not open v6 files.
- MP4 export uses FFmpeg to encode the embedded track as AAC and keeps the video duration matched to the animation.
- **Tab toggles Canvas Focus Mode**, hiding the top toolbar, settings panel, right layers panel, timeline and status area. Press again to restore previous visibility. It does not change the canvas zoom or selected tool.

## Installation

Update the four repository files using the usual Mac → GitHub → Surface workflow, then on your Surface:

```sh
cd ~/Projects/linux-animation-studio
git pull --ff-only
source .venv/bin/activate
python main.py
```

Requires `PySide6` (including Qt Multimedia) and **FFmpeg** (needed for MP3 waveform decoding and MP4 export). MP3 playback relies on Qt's installed multimedia backend.

## Testing

Test WAV and MP3 import, audio synchronization, waveform, waveform-click seeking and frame navigation, mute/volume, audio persistence after save/reopen, MP4 audio export, Tab focus mode and layout restoration, Space+drag Wacom navigation, and v0.19 regression. Use a backup copy of important projects before saving in v6.

This release passed Python syntax compilation and ZIP verification. The graphical application, audio backend, Wacom, and FFmpeg encoding have **not** been runtime-tested in this environment. One audio clip only; editing, trim, offsets, multiple tracks, and waveform scaling are future work.
