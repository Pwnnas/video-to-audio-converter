import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
from converter import VideoConverter


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class VideoToAudioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video to Audio Converter")
        self.root.geometry("700x580")
        self.root.resizable(True, True)
        self.root.minsize(580, 480)

        # Platform-aware styling
        self.style = ttk.Style()
        if sys.platform == "darwin":
            self.style.theme_use("aqua")
        elif sys.platform == "win32":
            self.style.theme_use("vista")
        else:
            self.style.theme_use("clam")

        self._configure_styles()

        self.converter = VideoConverter()
        self.files = []
        self.output_dir = tk.StringVar()
        self.is_converting = False

        # Check ffmpeg on startup
        self.root.after(200, self._check_ffmpeg)

        self._build_ui()

    # ------------------------------------------------------------------ #
    #  Styles                                                              #
    # ------------------------------------------------------------------ #

    def _configure_styles(self):
        """Extra style tweaks that work cross-platform."""
        if sys.platform == "win32":
            self.style.configure("TLabel", font=("Segoe UI", 10))
            self.style.configure("TButton", font=("Segoe UI", 10))
            self.style.configure("TCheckbutton", font=("Segoe UI", 10))
            self.style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        elif sys.platform == "darwin":
            self.style.configure("TLabel", font=("SF Pro Text", 12))
            self.style.configure("TButton", font=("SF Pro Text", 12))
            self.style.configure("TCheckbutton", font=("SF Pro Text", 12))
        else:
            self.style.configure("TLabel", font=("Helvetica", 10))
            self.style.configure("TButton", font=("Helvetica", 10))

    # ------------------------------------------------------------------ #
    #  UI construction                                                     #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        """Build all UI widgets."""

        # ── Title bar ─────────────────────────────────────────────────── #
        top_frame = ttk.Frame(self.root, padding=(12, 10, 12, 4))
        top_frame.pack(fill=tk.X)

        title_font = (
            ("SF Pro Display", 18, "bold")
            if sys.platform == "darwin"
            else ("Segoe UI", 16, "bold")
            if sys.platform == "win32"
            else ("Helvetica", 15, "bold")
        )
        ttk.Label(top_frame, text="🎬  Video → M4A Converter", font=title_font).pack(
            side=tk.LEFT
        )

        self.ffmpeg_status_label = ttk.Label(
            top_frame, text="", foreground="#888888"
        )
        self.ffmpeg_status_label.pack(side=tk.RIGHT, padx=4)

        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=12)

        # ── File list ─────────────────────────────────────────────────── #
        list_frame = ttk.LabelFrame(
            self.root, text="Video Files", padding=(10, 6)
        )
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 4))

        scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scroll_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL)

        list_font = (
            ("Courier New", 11)
            if sys.platform == "win32"
            else ("Menlo", 11)
            if sys.platform == "darwin"
            else ("Monospace", 10)
        )

        self.file_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.EXTENDED,
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
            activestyle="dotbox",
            font=list_font,
            bg="#f5f5f5" if sys.platform != "win32" else "white",
            bd=0,
            highlightthickness=1,
            highlightcolor="#aaaaaa",
            relief=tk.FLAT,
        )
        scroll_y.config(command=self.file_listbox.yview)
        scroll_x.config(command=self.file_listbox.xview)

        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Hint label shown when list is empty
        self.hint_label = ttk.Label(
            list_frame,
            text="Click  ➕ Add Files  to get started",
            foreground="#aaaaaa",
            font=("Segoe UI", 11, "italic")
            if sys.platform == "win32"
            else ("Helvetica", 11, "italic"),
        )
        self.hint_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # ── File-action buttons ───────────────────────────────────────── #
        btn_frame = ttk.Frame(self.root, padding=(12, 2))
        btn_frame.pack(fill=tk.X)

        ttk.Button(
            btn_frame, text="➕  Add Files", command=self._add_files, width=14
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            btn_frame,
            text="🗑  Remove Selected",
            command=self._remove_selected,
            width=18,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            btn_frame, text="✖  Clear All", command=self._clear_all, width=13
        ).pack(side=tk.LEFT)

        # ── Output directory ──────────────────────────────────────────── #
        out_frame = ttk.LabelFrame(
            self.root, text="Output Directory", padding=(10, 6)
        )
        out_frame.pack(fill=tk.X, padx=12, pady=(6, 4))

        out_row = ttk.Frame(out_frame)
        out_row.pack(fill=tk.X)

        self.out_entry = ttk.Entry(
            out_row,
            textvariable=self.output_dir,
            state="readonly",
            font=("Segoe UI", 10)
            if sys.platform == "win32"
            else ("Helvetica", 11),
        )
        self.out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        ttk.Button(
            out_row, text="📂  Browse", command=self._browse_output, width=13
        ).pack(side=tk.LEFT)

        self.same_dir_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            out_frame,
            text="Save next to original files",
            variable=self.same_dir_var,
            command=self._toggle_output_dir,
        ).pack(anchor=tk.W, pady=(4, 0))
        self._toggle_output_dir()

        # ── Options ───────────────────────────────────────────────────── #
        opt_frame = ttk.LabelFrame(self.root, text="Options", padding=(10, 6))
        opt_frame.pack(fill=tk.X, padx=12, pady=(0, 6))

        opt_row = ttk.Frame(opt_frame)
        opt_row.pack(fill=tk.X)

        ttk.Label(opt_row, text="Audio bitrate:").pack(side=tk.LEFT)

        self.bitrate_var = tk.StringVar(value="192k")
        ttk.Combobox(
            opt_row,
            textvariable=self.bitrate_var,
            values=["64k", "96k", "128k", "160k", "192k", "256k", "320k"],
            state="readonly",
            width=7,
        ).pack(side=tk.LEFT, padx=(8, 24))

        self.overwrite_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opt_row,
            text="Overwrite existing files",
            variable=self.overwrite_var,
        ).pack(side=tk.LEFT)

        # ── Progress ──────────────────────────────────────────────────── #
        prog_frame = ttk.Frame(self.root, padding=(12, 0, 12, 0))
        prog_frame.pack(fill=tk.X)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            prog_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 3))

        self.status_label = ttk.Label(
            prog_frame,
            text="Ready",
            foreground="#555555",
        )
        self.status_label.pack(anchor=tk.W)

        # ── Convert button ────────────────────────────────────────────── #
        bottom_frame = ttk.Frame(self.root, padding=(12, 4, 12, 12))
        bottom_frame.pack(fill=tk.X)

        self.convert_btn = ttk.Button(
            bottom_frame,
            text="▶  Convert to M4A",
            command=self._start_conversion,
            width=22,
        )
        self.convert_btn.pack(side=tk.RIGHT)

    # ------------------------------------------------------------------ #
    #  ffmpeg check                                                        #
    # ------------------------------------------------------------------ #

    def _check_ffmpeg(self):
        """Warn the user if ffmpeg cannot be found."""
        if self.converter.is_ffmpeg_available():
            self.ffmpeg_status_label.config(
                text="✅ ffmpeg ready", foreground="#2e7d32"
            )
        else:
            self.ffmpeg_status_label.config(
                text="⚠️ ffmpeg not found", foreground="#c62828"
            )
            msg = (
                "ffmpeg was not found on this system.\n\n"
                "Please install ffmpeg:\n"
            )
            if sys.platform == "win32":
                msg += (
                    "  • Download from https://ffmpeg.org/download.html\n"
                    "  • Or install via winget:  winget install ffmpeg\n"
                    "  • Or install via Chocolatey:  choco install ffmpeg\n\n"
                    "After installing, make sure ffmpeg.exe is in your PATH,\n"
                    "then restart this application."
                )
            elif sys.platform == "darwin":
                msg += "  • brew install ffmpeg"
            else:
                msg += "  • sudo apt install ffmpeg"

            messagebox.showerror("ffmpeg Not Found", msg)

    # ------------------------------------------------------------------ #
    #  File-list callbacks                                                 #
    # ------------------------------------------------------------------ #

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select Video Files",
            filetypes=[
                (
                    "Video files",
                    "*.mp4 *.mov *.avi *.mkv *.wmv *.flv *.webm *.m4v "
                    "*.mpeg *.mpg *.ts *.3gp",
                ),
                ("All files", "*.*"),
            ],
        )
        added = 0
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                # Show full path in listbox so Windows paths are readable
                self.file_listbox.insert(tk.END, p)
                added += 1

        if added:
            self._refresh_hint()
            self.status_label.config(
                text=f"{len(self.files)} file(s) queued"
            )

    def _remove_selected(self):
        selected = list(self.file_listbox.curselection())
        for idx in reversed(selected):
            self.file_listbox.delete(idx)
            del self.files[idx]
        self._refresh_hint()

    def _clear_all(self):
        self.file_listbox.delete(0, tk.END)
        self.files.clear()
        self._refresh_hint()
        self.status_label.config(text="Ready")
        self.progress_var.set(0)

    def _refresh_hint(self):
        if self.files:
            self.hint_label.place_forget()
        else:
            self.hint_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    # ------------------------------------------------------------------ #
    #  Output directory callbacks                                          #
    # ------------------------------------------------------------------ #

    def _browse_output(self):
        directory = filedialog.askdirectory(title="Choose Output Folder")
        if directory:
            self.output_dir.set(directory)

    def _toggle_output_dir(self):
        if self.same_dir_var.get():
            self.out_entry.config(state="disabled")
        else:
            self.out_entry.config(state="readonly")

    # ------------------------------------------------------------------ #
    #  Conversion                                                          #
    # ------------------------------------------------------------------ #

    def _start_conversion(self):
        if self.is_converting:
            return

        if not self.files:
            messagebox.showwarning("No Files", "Please add at least one video file.")
            return

        if not self.same_dir_var.get() and not self.output_dir.get():
            messagebox.showwarning(
                "No Output Directory", "Please choose an output directory."
            )
            return

        if not self.converter.is_ffmpeg_available():
            messagebox.showerror(
                "ffmpeg Not Found",
                "ffmpeg is not available. Cannot convert files.\n"
                "Please install ffmpeg and restart the application.",
            )
            return

        self.is_converting = True
        self.convert_btn.config(state=tk.DISABLED, text="⏳  Converting…")
        self.progress_var.set(0)

        thread = threading.Thread(target=self._run_conversion, daemon=True)
        thread.start()

    def _run_conversion(self):
        total = len(self.files)
        success_count = 0
        skipped_count = 0
        errors = []

        for i, input_path in enumerate(self.files):
            basename = os.path.basename(input_path)
            self._update_status(f"Converting {i + 1}/{total}: {basename}")

            # Determine output directory
            if self.same_dir_var.get():
                out_dir = os.path.dirname(input_path)
            else:
                out_dir = self.output_dir.get()

            stem = os.path.splitext(basename)[0]
            output_path = os.path.join(out_dir, stem + ".m4a")

            # Overwrite check
            if not self.overwrite_var.get() and os.path.exists(output_path):
                skipped_count += 1
                errors.append(f"SKIPPED  {basename}  →  output already exists")
                self._update_progress((i + 1) / total * 100)
                continue

            ok, error_msg = self.converter.convert(
                input_path, output_path, bitrate=self.bitrate_var.get()
            )
            if ok:
                success_count += 1
            else:
                errors.append(f"ERROR    {basename}  →  {error_msg}")

            self._update_progress((i + 1) / total * 100)

        self._finish_conversion(success_count, skipped_count, errors, total)

    # ------------------------------------------------------------------ #
    #  Thread-safe UI helpers                                              #
    # ------------------------------------------------------------------ #

    def _update_status(self, msg: str):
        self.root.after(0, lambda: self.status_label.config(text=msg))

    def _update_progress(self, value: float):
        self.root.after(0, lambda: self.progress_var.set(value))

    def _finish_conversion(
        self, success: int, skipped: int, errors: list, total: int
    ):
        def _do():
            self.is_converting = False
            self.convert_btn.config(state=tk.NORMAL, text="▶  Convert to M4A")
            self.progress_var.set(100)

            failed = len(errors) - skipped

            if errors:
                detail = "\n".join(errors)
                msg = (
                    f"Converted : {success}/{total}\n"
                    f"Skipped   : {skipped}\n"
                    f"Failed    : {failed}\n\n"
                    f"Details:\n{detail}"
                )
                messagebox.showwarning("Conversion Complete (with issues)", msg)
            else:
                messagebox.showinfo(
                    "Conversion Complete",
                    f"✅  Successfully converted {success} file(s).",
                )

            self.status_label.config(
                text=f"Done — {success} converted, {skipped} skipped, {failed} failed"
            )

        self.root.after(0, _do)


# ------------------------------------------------------------------ #
#  Entry point                                                         #
# ------------------------------------------------------------------ #

def main():
    root = tk.Tk()

    # Windows: tell Windows this is a DPI-aware application
    if sys.platform == "win32":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    app = VideoToAudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()