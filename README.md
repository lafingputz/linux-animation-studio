# Linux Animation Studio v0.23.0

Cross-platform preparation release based on the validated v0.22.0 branch.

## What's new

- **Cross-platform brush data directory.** Linux intentionally retains the existing `$XDG_DATA_HOME/linux-animation-studio/brushes` (or `~/.local/share/linux-animation-studio/brushes`) directory. Windows and macOS use Qt's standard per-user application-data folder. This does not move or delete existing Linux brushes.
- **FFmpeg discovery.** WAV/MP3 waveform decoding and MP4 export locate FFmpeg using `LAS_FFMPEG_PATH`, an executable alongside the Python/packaged app, or system `PATH`. An error message no longer assumes Ubuntu or apt.
- **Multi-frame Edit warning.** The transport row displays an orange `MULTI-FRAME EDIT ON (N selected)` label whenever batch editing is enabled, even while the Cels tab is hidden.
- **Application version:** v0.23.0. `.las` file format **remains v6**, and the documented launch method is unchanged.

## Run from source (Linux, Windows or macOS)

Install Python 3, create a virtual environment, and install the requirements:

```sh
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Activate the environment before installing/running if desired. On Linux/macOS: `source .venv/bin/activate`; on Windows PowerShell: `.venv\\Scripts\\Activate.ps1`. If `python` maps to a different installation, use `python3` or the Windows `py` launcher.

**For the existing Surface Pro 3 workflow:** keep your existing repository and `.venv`, pull the latest commit, then `python main.py` as before.

FFmpeg must be separately installed for MP3 waveform decoding and MP4 export, unless an executable has been provided alongside the application. Put it on `PATH` or set `LAS_FFMPEG_PATH` to the executable (for example, on Windows, `C:\\ffmpeg\\bin\\ffmpeg.exe`). Audio playback uses Qt Multimedia and depends on codecs available in the target environment.

## Experimental builds (not prebuilt binaries)

Packaging requires building **on each target OS** with matching Python/PySide6 architecture. PyInstaller is one possible development packaging option:

```sh
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --name LinuxAnimationStudio main.py
```

Test the `dist/LinuxAnimationStudio` output on the **same target operating system**. On macOS the output may be an `.app` bundle; on Windows an executable directory. Do not assume an archive built on Linux will run on Windows or macOS. Bundling FFmpeg requires separate binary distribution and licensing review. Public macOS releases also need appropriate signing/notarization. These builds are experimental; installers, signing, and shipping standalone binaries are **not** included in this four-file source ZIP.

## Cross-platform acceptance tests

1. **Linux:** existing brush presets and `.las` files load in place; check all v0.22 editing and audio regressions.
2. **Windows/macOS:** launch from source; create a project, draw, save/reopen; check tablet pressure and event handling on connected pen hardware.
3. **Keyboard:** verify Cmd/Ctrl conventions and saved custom shortcuts, including Space+drag, playback, and Focus Mode.
4. **Audio:** import WAV/MP3, seek/play, save/reopen the embedded track, export MP4 with FFmpeg available.
5. **Display:** check Wacom/canvas alignment at 100%, 200%, and high-DPI/Retina scaling; window resize and timeline behavior.
6. **Portability:** transfer an embedded-audio `.las` v6 project between operating systems and validate drawings, cel relationships, and playback.
7. **Mode awareness:** choose multiple frames, enable Multi-frame Edit, confirm orange label stays visible while switching tabs, then disable it.
8. **Packaging:** optionally build and launch a PyInstaller development bundle on Windows/macOS; confirm resource paths and FFmpeg behavior.

## Known limitations

- Windows and macOS **have not yet been run or hardware-tested** for this build. Tablet drivers and Qt Multimedia backend availability vary.
- Qt6 supports high-DPI scaling, but alignment on actual Retina/Windows fractional-scaling hardware needs testing.
- Multi-frame Edit remains opt-in to protect against accidental changes to several drawings.
- Audible scrubbing is not implemented; waveform dragging seeks the timeline.
- This release preserves the single-file `main.py` source architecture. Modularization remains future work.
- `.las` format version 6 may not be readable by older app releases. Backup important projects before editing them with a development build.
