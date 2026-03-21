import subprocess
import os
import sys
import shutil
import threading


def _ffmpeg_path() -> str:
    """
    Resolve the ffmpeg binary path.

    Priority:
    1. Bundled binary inside PyInstaller package (_MEIPASS)
    2. System PATH
    """
    binary_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"

    if hasattr(sys, "_MEIPASS"):
        bundled = os.path.join(sys._MEIPASS, binary_name)
        if os.path.isfile(bundled):
            return bundled
        bundled_bare = os.path.join(sys._MEIPASS, "ffmpeg")
        if os.path.isfile(bundled_bare):
            return bundled_bare

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    return binary_name


def _ffprobe_path() -> str:
    """Resolve the ffprobe binary path (used for duration queries)."""
    binary_name = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"

    # Try same directory as resolved ffmpeg first
    ffmpeg = _ffmpeg_path()
    ffmpeg_dir = os.path.dirname(ffmpeg)
    if ffmpeg_dir:
        candidate = os.path.join(ffmpeg_dir, binary_name)
        if os.path.isfile(candidate):
            return candidate

    system = shutil.which("ffprobe")
    if system:
        return system

    return binary_name


def _subprocess_flags() -> dict:
    """Prevent a console window from flashing on Windows."""
    flags = {}
    if sys.platform == "win32":
        CREATE_NO_WINDOW = 0x08000000
        flags["creationflags"] = CREATE_NO_WINDOW
    return flags


# Maps format name → (codec_args, supports_bitrate)
FORMAT_CONFIGS: dict[str, tuple[list[str], bool]] = {
    "m4a":  (["-acodec", "aac", "-movflags", "+faststart"], True),
    "mp3":  (["-acodec", "libmp3lame"], True),
    "wav":  (["-acodec", "pcm_s16le"], False),
    "flac": (["-acodec", "flac"], False),
    "ogg":  (["-acodec", "libvorbis"], True),
}


class VideoConverter:
    """Wraps ffmpeg to extract audio from video files."""

    SUPPORTED_EXTENSIONS = {
        ".mp4", ".mov", ".avi", ".mkv", ".wmv",
        ".flv", ".webm", ".m4v", ".mpeg", ".mpg",
        ".ts", ".3gp",
    }

    SUPPORTED_FORMATS = list(FORMAT_CONFIGS.keys())

    def __init__(self):
        self.ffmpeg = _ffmpeg_path()
        self.ffprobe = _ffprobe_path()

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

    def get_duration(self, input_path: str) -> float:
        """Return the media duration in seconds, or 0.0 on failure."""
        try:
            result = subprocess.run(
                [
                    self.ffprobe,
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    input_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=30,
                **_subprocess_flags(),
            )
            return float(result.stdout.decode().strip())
        except Exception:
            return 0.0

    # ------------------------------------------------------------------ #

    def convert(
        self,
        input_path: str,
        output_path: str,
        bitrate: str = "192k",
        fmt: str = "m4a",
        progress_callback=None,  # callable(float 0–100) or None
    ) -> tuple[bool, str]:
        """
        Convert *input_path* to audio at *output_path*.

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

        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.isdir(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except OSError as e:
                return False, f"Cannot create output directory: {e}"

        codec_args, supports_bitrate = FORMAT_CONFIGS.get(fmt, FORMAT_CONFIGS["m4a"])
        codec_args = list(codec_args)
        if supports_bitrate:
            codec_args += ["-b:a", bitrate]

        # Determine whether we can show per-file progress
        duration = 0.0
        if progress_callback is not None:
            duration = self.get_duration(input_path)
        use_progress = progress_callback is not None and duration > 0

        cmd = [self.ffmpeg, "-y", "-i", input_path, "-vn"] + codec_args
        if use_progress:
            cmd += ["-progress", "pipe:1", "-nostats"]
        cmd.append(output_path)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **_subprocess_flags(),
            )

            # Drain stderr in a background thread to prevent pipe-buffer deadlock
            stderr_lines: list[str] = []

            def _drain_stderr():
                for raw in process.stderr:
                    stderr_lines.append(raw.decode("utf-8", errors="replace").rstrip())

            stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
            stderr_thread.start()

            if use_progress:
                # Parse structured progress output from stdout
                for raw in process.stdout:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line.startswith("out_time_ms="):
                        try:
                            ms = int(line.split("=", 1)[1])
                            if ms >= 0:
                                pct = min(99.9, ms / 1_000_000 / duration * 100)
                                progress_callback(pct)
                        except (ValueError, IndexError):
                            pass
            else:
                # Still drain stdout so the pipe doesn't block
                process.stdout.read()

            process.wait(timeout=3600)
            stderr_thread.join(timeout=5)

            if process.returncode != 0:
                lines = [ln for ln in stderr_lines if ln.strip()]
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
            process.kill()
            return False, "Conversion timed out (> 1 hour)."
        except OSError as e:
            return False, f"OS error: {e}"
        except Exception as e:
            return False, f"Unexpected error: {e}"
