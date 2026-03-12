#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# macOS / Linux build script
# Usage:
#   chmod +x build.sh && ./build.sh
#
# Prerequisites:
#   macOS  : brew install ffmpeg && pip install pyinstaller
#   Linux  : sudo apt install ffmpeg && pip install pyinstaller
# ---------------------------------------------------------------------------
#set -euo pipefail

APP_NAME="VideoToAudioConverter"
FFMPEG_PATH="$(which ffmpeg 2>/dev/null || true)"

if [[ -z "$FFMPEG_PATH" ]]; then
    echo "❌  ffmpeg not found."
    if [[ "$(uname)" == "Darwin" ]]; then
        echo "    Install with:  brew install ffmpeg"
    else
        echo "    Install with:  sudo apt install ffmpeg"
    fi
    exit 1
fi

echo "✅  Found ffmpeg at: $FFMPEG_PATH"
echo "🔨  Building $APP_NAME ..."

# Clean previous build
rm -rf build dist "${APP_NAME}.spec"

pyinstaller \
    --noconfirm \
    --onefile \
    --windowed \
    --name "$APP_NAME" \
    --add-binary "$FFMPEG_PATH:." \
    --hidden-import tkinter \
    --hidden-import tkinter.ttk \
    --hidden-import tkinter.filedialog \
    --hidden-import tkinter.messagebox \
    $( [[ "$(uname)" == "Darwin" ]] && echo '--osx-bundle-identifier com.yourname.videotoaudio' ) \
    main.py

echo ""
echo "✅  Build complete!"
if [[ "$(uname)" == "Darwin" ]]; then
    echo "📦  App bundle : dist/${APP_NAME}.app"
fi
echo "💿  Binary     : dist/${APP_NAME}"
