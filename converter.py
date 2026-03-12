import subprocess
import os
import sys
import shutil


def _ffmpeg_path() -> str:
    """
    Resolve the ffmpeg binary path.

    Priority:
    1. Bundled binary inside PyInstaller package (_MEIPASS)
    2. System PATH
    """
    binary_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"

    # PyInstaller bundle
    if hasattr(sys, "_MEIPASS"):
        bundled = os.path.join(sys._MEIPASS, binary_name)
        if os.path.isfile(bundled):
            return bundled
        # Also try without .exe suffix just in case
        bundled_bare = os.path.join(sys._MEIPASS, "ffmpeg")
        if os.path.isfile(bundled_bare):
            return bundled_bare

    # System PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    # Last resort – let subprocess raise a clear FileNotFoundError
    return binary_name


def _subprocess_flags() -> dict:
    """
    On Windows, prevent a console window from flashing when
    ffmpeg is spawned from a windowed (--windowed) PyInstaller app.
    """
    flags = {}
    if sys.platform == "win32":
        CREATE_NO_WINDOW = 0x08000000
        flags["creationflags"] = CREATE_NO_WINDOW
    return flags


class VideoConverter:
    """Wraps ffmpeg to extract audio from video files and save as M4A."""

    SUPPORTED_EXTENSIONS = {
        ".mp4", ".mov", ".avi", ".mkv", ".wmv",
        ".flv", ".webm", ".m4v", ".mpeg", ".mpg",
        ".ts", ".3gp",
    }

    def __init__(self):
        self.ffmpeg = _ffmpeg_path()

    # ------------------------------------------------------------------ #

    def is_ffmpeg_available(self) -> bool:
        """Return True if ffmpeg can be found and executed."""
        try:
            subprocess.run(
                [self.ffmpeg, "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                **_subprocess_flags(),
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError, OSError):
            return False

    # ------------------------------------------------------------------ #

    def convert(
        self,
        input_path: str,
        output_path: str,
        bitrate: str = "192k",
    ) -> tuple[bool, str]:
        """
        Convert *input_path* to M4A audio at *output_path*.

        Returns
        -------
        (True,  "")           on success
        (False, error_msg)    on failure
        """
        if not os.path.isfile(input_path):
            return False, f"Input file not found: {input_path}"

        ext = os.path.splitext(input_path)[1].lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            return False, f"Unsupported file extension: {ext}"

        # Ensure output directory exists
        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.isdir(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except OSError as e:
                return False, f"Cannot create output directory: {e}"

        cmd = [
            self.ffmpeg,
            "-y",                    # overwrite output (guard handled in UI)
            "-i", input_path,
            "-vn",                   # drop video stream
            "-acodec", "aac",        # AAC codec → required for .m4a
            "-b:a", bitrate,
            "-movflags", "+faststart",
            output_path,
        ]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=3600,
                **_subprocess_flags(),
            )
            if result.returncode != 0:
                stderr_text = result.stderr.decode("utf-8", errors="replace")
                lines = [ln.strip() for ln in stderr_text.splitlines() if ln.strip()]
                short_error = lines[-1] if lines else "Unknown ffmpeg error"
                return False, short_error
            return True, ""

        except FileNotFoundError:
            return (
                False,
                "ffmpeg executable not found. "
                "Please install ffmpeg and add it to your PATH.",
            )
        except subprocess.TimeoutExpired:
            return False, "Conversion timed out (> 1 hour)."
        except OSError as e:
            return False, f"OS error: {e}"
        except Exception as e:  # noqa: BLE001
            return False, f"Unexpected error: {e}"