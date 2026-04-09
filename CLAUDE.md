# CLAUDE.md

This file provides guidance for AI assistants working with this codebase.

## Project Overview

**Video to Audio Converter** is a cross-platform desktop GUI application that extracts audio from video files using ffmpeg. It is written in Python and packaged as a standalone executable (no Python or ffmpeg installation required by end users).

- **Language**: Python 3.11+
- **UI Framework**: tkinter + tkinterdnd2 (drag-and-drop support)
- **Conversion Backend**: ffmpeg (bundled into release executables)
- **Packaging**: PyInstaller
- **CI/CD**: GitHub Actions (builds on version tags)

---

## Repository Structure

```
video-to-audio-converter/
├── main.py                       # UI layer — tkinter app (VideoToAudioApp)
├── converter.py                  # Logic layer — ffmpeg wrapper (VideoConverter)
├── requirements.txt              # Runtime Python dependencies
├── VideoToAudioConverter.spec    # PyInstaller build spec
├── build.sh                      # macOS/Linux build script
├── build.bat                     # Windows build script
├── README.md                     # End-user documentation
└── .github/
    └── workflows/
        └── build.yml             # CI/CD: builds executables on tag push
```

---

## Architecture

The project follows a strict two-layer separation:

### `main.py` — UI Layer
- Class: `VideoToAudioApp`
- Owns all tkinter widgets and event handlers
- Uses background threading for conversions (never blocks the main loop)
- Uses `root.after()` for all thread-safe UI updates
- Reads ffmpeg availability at startup and shows a user-friendly error if missing
- Writes history to `~/.video_converter_history.log`

### `converter.py` — Logic Layer
- Class: `VideoConverter`
- No tkinter imports — pure conversion logic
- Resolves ffmpeg/ffprobe from bundled path (PyInstaller) or system PATH
- Accepts a `progress_callback(fraction: float)` for real-time UI feedback
- Returns `(success: bool, message: str)` tuples; never raises exceptions to callers
- Parses ffmpeg's `out_time_ms=` stdout output for progress estimation

**Rule**: `main.py` must never call ffmpeg directly. `converter.py` must never import tkinter.

---

## Supported Formats

**Input (video)**: MP4, MOV, AVI, MKV, WMV, FLV, WebM, M4V, MPEG, MPG, TS, 3GP  
**Output (audio)**: M4A (AAC), MP3, WAV, FLAC, OGG  
**Bitrates**: 64k, 96k, 128k, 192k, 256k, 320k (not applicable to WAV/FLAC)

---

## Development Setup

```bash
# Install Python 3.11+, then:
pip install -r requirements.txt

# Run from source (requires ffmpeg on PATH)
python main.py
```

`requirements.txt` only contains `tkinterdnd2>=0.4.0`. PyInstaller is a build-time dependency only and is not listed there.

---

## Building Executables

### macOS / Linux
```bash
bash build.sh
```
- Requires: `ffmpeg` on PATH, `pyinstaller` installed
- Locates the ffmpeg binary, bundles it into a single-file executable
- On macOS, also creates a `.app` bundle

### Windows
```bat
build.bat
```
- Requires: `ffmpeg` installed (via winget or Chocolatey), `pyinstaller` installed
- Bundles `ffmpeg.exe` into a single `.exe`

### CI/CD (GitHub Actions)
- Triggered by pushing a version tag: `git tag v1.x.x && git push --tags`
- Builds for **macOS (arm64)** and **Windows** in parallel
- Downloads static ffmpeg builds (no Homebrew/Chocolatey dependency in CI)
- Validates artifact size > 20 MB (ensures ffmpeg is bundled)
- Uploads artifacts with 30-day retention

---

## Code Conventions

### Naming
- Private methods: `_snake_case()` (leading underscore)
- Public methods: `snake_case()`
- Class attributes: `snake_case`
- Theme/constant dicts: `UPPER_CASE` (e.g., `DARK`, `LIGHT`)

### Section Delimiters
Visual separators are used in both files to mark logical sections:
```python
# ──────────────────────────────────────────────
```

### Platform Detection
```python
if sys.platform == "win32":   # Windows
elif sys.platform == "darwin": # macOS
else:                           # Linux
```
This pattern is used for fonts, subprocess flags, and paths. Always handle all three cases.

### Threading
- Conversion runs on a `threading.Thread`
- UI updates from threads must use `root.after(0, callback)` — never call tkinter methods directly from worker threads

### Resource Paths (PyInstaller Compatibility)
`converter.py` uses `sys._MEIPASS` to locate bundled binaries when running as a packaged executable. When modifying binary resolution logic, maintain compatibility with both running-from-source and running-as-executable modes.

### Error Handling
- `VideoConverter` methods return `(bool, str)` — do not raise exceptions to callers
- UI shows errors via `messagebox.showerror()` for blocking errors, or appends to the log area for per-file errors
- Always validate file extensions before attempting conversion

### Type Hints
Use Python 3.11+ type hints in all new function signatures.

---

## Testing

There are no automated tests in this project. Validation is done by:
1. Running `python main.py` and testing manually
2. CI artifact size check (>20 MB confirms ffmpeg is bundled)

When adding significant logic, consider adding `pytest` unit tests — especially for `converter.py` which has no UI dependencies.

---

## Key Files to Understand First

When working on this repo, read these files in order:
1. `converter.py` — understand the ffmpeg abstraction
2. `main.py` — understand the UI and how it calls `VideoConverter`
3. `build.sh` / `build.bat` — understand the packaging process
4. `.github/workflows/build.yml` — understand CI/CD

---

## Common Tasks

### Add a new output format
1. Add the format string to `VideoConverter.AUDIO_FORMATS` in `converter.py`
2. Add the ffmpeg codec mapping in `VideoConverter._get_codec()` in `converter.py`
3. Add the format option to the UI dropdown in `main.py` (`self._format_var` default and options)

### Add a new input video format
1. Add the extension to `VideoConverter.VIDEO_EXTENSIONS` in `converter.py`
2. Add it to the file dialog filter in `main.py` (`_add_files()` method)

### Change UI theme colors
Modify the `DARK` and `LIGHT` dicts near the top of `main.py`. Both dicts must define the same keys.

### Bump the version for a release
1. Update version references if any exist in the codebase
2. Commit all changes
3. Tag the commit: `git tag v1.x.x && git push --tags`
4. GitHub Actions will build and upload artifacts automatically
