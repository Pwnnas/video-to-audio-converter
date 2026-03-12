@echo off
setlocal enabledelayedexpansion
:: ---------------------------------------------------------------------------
:: Windows build script
:: Usage: Double-click build.bat  OR  run from a Developer / normal CMD prompt
::
:: Prerequisites:
::   winget install ffmpeg        (or choco install ffmpeg)
::   pip install pyinstaller
:: ---------------------------------------------------------------------------

set APP_NAME=VideoToAudioConverter

echo.
echo ============================================================
echo  Video to Audio Converter - Windows Build
echo ============================================================
echo.

:: ── Locate ffmpeg ─────────────────────────────────────────────────────────
where ffmpeg >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] ffmpeg.exe not found in PATH.
    echo.
    echo  Install options:
    echo    winget install ffmpeg
    echo    choco install ffmpeg
    echo    Or download from https://ffmpeg.org/download.html
    echo.
    echo  After installing, re-run this script.
    pause
    exit /b 1
)

for /f "delims=" %%i in ('where ffmpeg') do (
    set FFMPEG_PATH=%%i
    goto :found_ffmpeg
)
:found_ffmpeg
echo [OK] Found ffmpeg at: %FFMPEG_PATH%

:: ── Locate PyInstaller ─────────────────────────────────────────────────────
where pyinstaller >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] pyinstaller not found.
    echo  Install with:  pip install pyinstaller
    pause
    exit /b 1
)
echo [OK] PyInstaller found.

:: ── Clean previous build ───────────────────────────────────────────────────
echo.
echo Cleaning previous build artefacts...
if exist build     rmdir /s /q build
if exist dist      rmdir /s /q dist
if exist "%APP_NAME%.spec" del /q "%APP_NAME%.spec"

:: ── Run PyInstaller ────────────────────────────────────────────────────────
echo.
echo Building %APP_NAME%.exe ...
echo.

pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "%APP_NAME%" ^
    --add-binary "%FFMPEG_PATH%;." ^
    --hidden-import tkinter ^
    --hidden-import tkinter.ttk ^
    --hidden-import tkinter.filedialog ^
    --hidden-import tkinter.messagebox ^
    main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] PyInstaller failed. See output above.
    pause
    exit /b 1
)

:: ── Done ───────────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo  Build complete!
echo  Executable: dist\%APP_NAME%.exe
echo ============================================================
echo.
pause