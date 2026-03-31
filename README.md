# Video to Audio Converter

A desktop app that extracts audio from video files. Drop in a video, pick your output format, and get the audio — no command line needed.

## Features

- **Drag and drop** video files directly into the app
- **Multiple output formats**: MP3, M4A, WAV, FLAC, OGG
- **Real progress bar** with time remaining
- **Conversion history log** in the app
- **Dark mode** support (Apple-inspired UI)
- **Standalone executable** — ffmpeg is bundled, nothing extra to install

## Supported input formats

MP4, MOV, AVI, MKV, WMV, FLV, WebM, M4V, MPEG, MPG, TS, 3GP

## Download

Pre-built executables are built automatically via GitHub Actions when a version tag is pushed:

- **Windows** — `VideoToAudioConverter.exe`
- **macOS** — `VideoToAudioConverter.app` (arm64)

Go to the [Actions](../../actions) tab to grab the latest build artifact, or check [Releases](../../releases) if one has been published.

## Run from source

**Requirements:** Python 3.11+, ffmpeg on your PATH (or let the build bundle it)

```bash
pip install -r requirements.txt
python main.py
```

## Build a standalone executable

```bash
# macOS / Linux
bash build.sh

# Windows
build.bat
```

The build scripts use PyInstaller and bundle a static ffmpeg binary so the output executable has no external dependencies.

## Tech stack

- **UI:** tkinter + tkinterdnd2 (drag and drop)
- **Conversion:** ffmpeg (via subprocess)
- **Packaging:** PyInstaller
- **CI:** GitHub Actions (builds for Windows and macOS on every version tag)
