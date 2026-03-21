import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import datetime
from converter import VideoConverter

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ------------------------------------------------------------------ #
#  Theme colour palettes                                               #
# ------------------------------------------------------------------ #

LIGHT_THEME = {
    "bg":           "#f0f0f0",
    "fg":           "#1a1a1a",
    "listbox_bg":   "#f5f5f5",
    "listbox_fg":   "#1a1a1a",
    "entry_bg":     "#ffffff",
    "select_bg":    "#0078d4",
    "select_fg":    "#ffffff",
    "status_fg":    "#555555",
    "hint_fg":      "#aaaaaa",
    "ffmpeg_ok":    "#2e7d32",
    "ffmpeg_err":   "#c62828",
    "progress_bar": "#0078d4",
    "trough":       "#d0d0d0",
}

DARK_THEME = {
    "bg":           "#1e1e1e",
    "fg":           "#d4d4d4",
    "listbox_bg":   "#252526",
    "listbox_fg":   "#d4d4d4",
    "entry_bg":     "#3c3c3c",
    "select_bg":    "#094771",
    "select_fg":    "#ffffff",
    "status_fg":    "#9e9e9e",
    "hint_fg":      "#555555",
    "ffmpeg_ok":    "#4caf50",
    "ffmpeg_err":   "#ef5350",
    "progress_bar": "#1e88e5",
    "trough":       "#3c3c3c",
}


def _parse_dnd_paths(data: str) -> list[str]:
    """Parse tkinterdnd2 drop data (handles space-separated and brace-quoted paths)."""
    paths: list[str] = []
    current = ""
    in_braces = False
    for ch in data:
        if ch == "{":
            in_braces = True
        elif ch == "}":
            in_braces = False
            if current:
                paths.append(current)
                current = ""
        elif ch == " " and not in_braces:
            if current:
                paths.append(current)
                current = ""
        else:
            current += ch
    if current:
        paths.append(current)
    return paths


# ------------------------------------------------------------------ #
#  Main application                                                    #
# ------------------------------------------------------------------ #

class VideoToAudioApp:
    LOG_FILE = os.path.expanduser("~/.video_converter_history.log")

    def __init__(self, root):
        self.root = root
        self.root.title("Video to Audio Converter")
        self.root.geometry("820x780")
        self.root.resizable(True, True)
        self.root.minsize(640, 600)

        # Detect the platform's default theme so we can restore it from dark mode
        if sys.platform == "darwin":
            self._platform_theme = "aqua"
        elif sys.platform == "win32":
            self._platform_theme = "vista"
        else:
            self._platform_theme = "clam"

        self.style = ttk.Style()
        self.style.theme_use(self._platform_theme)
        self._configure_fonts()

        self.converter = VideoConverter()
        self.files: list[str] = []
        self.output_dir = tk.StringVar()
        self.is_converting = False
        self.dark_mode = tk.BooleanVar(value=False)

        self.root.after(200, self._check_ffmpeg)
        self._build_ui()
        self._apply_theme()

    # ------------------------------------------------------------------ #
    #  Fonts / styles                                                      #
    # ------------------------------------------------------------------ #

    def _configure_fonts(self):
        if sys.platform == "win32":
            self.style.configure("TLabel",          font=("Segoe UI", 13))
            self.style.configure("TButton",         font=("Segoe UI", 15))
            self.style.configure("TCheckbutton",    font=("Segoe UI", 15))
            self.style.configure("TLabelframe.Label", font=("Segoe UI", 13, "bold"))
        elif sys.platform == "darwin":
            self.style.configure("TLabel",          font=("SF Pro Text", 14))
            self.style.configure("TButton",         font=("SF Pro Text", 14))
            self.style.configure("TCheckbutton",    font=("SF Pro Text", 14))
        else:
            self.style.configure("TLabel",          font=("Helvetica", 15))
            self.style.configure("TButton",         font=("Helvetica", 15))

    # ------------------------------------------------------------------ #
    #  UI construction                                                     #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        # ── Title bar ─────────────────────────────────────────────────── #
        top_frame = ttk.Frame(self.root, padding=(14, 10, 12, 4))
        top_frame.pack(fill=tk.X)

        title_font = (
            ("SF Pro Display", 16, "bold") if sys.platform == "darwin"
            else ("Segoe UI",   16, "bold") if sys.platform == "win32"
            else ("Helvetica",  16, "bold")
        )
        ttk.Label(top_frame, text="🎬  Video → Audio Converter", font=title_font).pack(
            side=tk.LEFT
        )

        # Right side of title bar: dark mode toggle + ffmpeg badge
        right_bar = ttk.Frame(top_frame)
        right_bar.pack(side=tk.RIGHT)

        self.dark_btn = ttk.Checkbutton(
            right_bar,
            text="🌙 Dark",
            variable=self.dark_mode,
            command=self._apply_theme,
        )
        self.dark_btn.pack(side=tk.LEFT, padx=(0, 12))

        self.ffmpeg_status_label = ttk.Label(right_bar, text="", foreground="#888888")
        self.ffmpeg_status_label.pack(side=tk.LEFT, padx=4)

        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=14)

        # ── File list ─────────────────────────────────────────────────── #
        list_frame = ttk.LabelFrame(self.root, text="Video Files", padding=(14, 6))
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(9, 4))

        scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scroll_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL)

        list_font = (
            ("Courier New", 13) if sys.platform == "win32"
            else ("Menlo",      14) if sys.platform == "darwin"
            else ("Monospace",  14)
        )

        self.file_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.EXTENDED,
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
            activestyle="dotbox",
            font=list_font,
            bg="#f5f5f5",
            fg="#1a1a1a",
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

        # Drag-and-drop support
        if HAS_DND:
            self.file_listbox.drop_target_register(DND_FILES)
            self.file_listbox.dnd_bind("<<Drop>>", self._on_drop)

        hint_text = (
            "Drop files here  or  click  ➕ Add Files" if HAS_DND
            else "Click  ➕ Add Files  to get started"
        )
        self.hint_label = ttk.Label(
            list_frame,
            text=hint_text,
            foreground="#aaaaaa",
            font=(
                ("Segoe UI",   12, "italic") if sys.platform == "win32"
                else ("Helvetica", 12, "italic")
            ),
        )
        self.hint_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # ── File-action buttons ───────────────────────────────────────── #
        btn_frame = ttk.Frame(self.root, padding=(14, 3))
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="➕  Add Files",        command=self._add_files,       width=14).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="🗑  Remove Selected", command=self._remove_selected,  width=18).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="✖  Clear All",        command=self._clear_all,        width=13).pack(side=tk.LEFT)

        # ── Output directory ──────────────────────────────────────────── #
        out_frame = ttk.LabelFrame(self.root, text="Output Directory", padding=(12, 6))
        out_frame.pack(fill=tk.X, padx=14, pady=(6, 4))

        out_row = ttk.Frame(out_frame)
        out_row.pack(fill=tk.X)

        self.out_entry = ttk.Entry(
            out_row,
            textvariable=self.output_dir,
            state="readonly",
            font=("Segoe UI", 12) if sys.platform == "win32" else ("Helvetica", 12),
        )
        self.out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        ttk.Button(out_row, text="📂  Browse", command=self._browse_output, width=13).pack(side=tk.LEFT)

        self.same_dir_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            out_frame,
            text="Save next to original files",
            variable=self.same_dir_var,
            command=self._toggle_output_dir,
        ).pack(anchor=tk.W, pady=(4, 0))
        self._toggle_output_dir()

        # ── Options ───────────────────────────────────────────────────── #
        opt_frame = ttk.LabelFrame(self.root, text="Options", padding=(12, 6))
        opt_frame.pack(fill=tk.X, padx=12, pady=(0, 6))

        opt_row = ttk.Frame(opt_frame)
        opt_row.pack(fill=tk.X)

        ttk.Label(opt_row, text="Output format:").pack(side=tk.LEFT)
        self.format_var = tk.StringVar(value="m4a")
        self.format_combo = ttk.Combobox(
            opt_row,
            textvariable=self.format_var,
            values=VideoConverter.SUPPORTED_FORMATS,
            state="readonly",
            width=6,
        )
        self.format_combo.pack(side=tk.LEFT, padx=(8, 24))
        self.format_combo.bind("<<ComboboxSelected>>", self._on_format_change)

        ttk.Label(opt_row, text="Audio bitrate:").pack(side=tk.LEFT)
        self.bitrate_var = tk.StringVar(value="192k")
        self.bitrate_combo = ttk.Combobox(
            opt_row,
            textvariable=self.bitrate_var,
            values=["64k", "96k", "128k", "160k", "192k", "256k", "320k"],
            state="readonly",
            width=7,
        )
        self.bitrate_combo.pack(side=tk.LEFT, padx=(8, 24))

        self.overwrite_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opt_row,
            text="Overwrite existing files",
            variable=self.overwrite_var,
        ).pack(side=tk.LEFT)

        # ── Progress ──────────────────────────────────────────────────── #
        prog_frame = ttk.Frame(self.root, padding=(14, 0, 12, 0))
        prog_frame.pack(fill=tk.X)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            prog_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 3))

        self.status_label = ttk.Label(prog_frame, text="Ready", foreground="#555555")
        self.status_label.pack(anchor=tk.W)

        # ── Bottom buttons ────────────────────────────────────────────── #
        bottom_frame = ttk.Frame(self.root, padding=(14, 4, 12, 14))
        bottom_frame.pack(fill=tk.X)

        self.convert_btn = ttk.Button(
            bottom_frame,
            text="▶  Convert to M4A",
            command=self._start_conversion,
            width=22,
        )
        self.convert_btn.pack(side=tk.RIGHT)

        ttk.Button(
            bottom_frame,
            text="📋  View Log",
            command=self._view_log,
            width=14,
        ).pack(side=tk.RIGHT, padx=(0, 8))

    # ------------------------------------------------------------------ #
    #  Theme                                                               #
    # ------------------------------------------------------------------ #

    def _apply_theme(self):
        c = DARK_THEME if self.dark_mode.get() else LIGHT_THEME

        # "clam" is the most customisable theme; use it for dark mode.
        # Restore the platform theme when switching back to light.
        if self.dark_mode.get():
            self.style.theme_use("clam")
        else:
            self.style.theme_use(self._platform_theme)
        self._configure_fonts()  # re-apply fonts after theme switch

        # ttk-wide overrides
        self.style.configure(".",                   background=c["bg"], foreground=c["fg"])
        self.style.configure("TFrame",              background=c["bg"])
        self.style.configure("TLabel",              background=c["bg"], foreground=c["fg"])
        self.style.configure("TLabelframe",         background=c["bg"])
        self.style.configure("TLabelframe.Label",   background=c["bg"], foreground=c["fg"])
        self.style.configure("TCheckbutton",        background=c["bg"], foreground=c["fg"])
        self.style.configure("TCombobox",           fieldbackground=c["entry_bg"], foreground=c["fg"], background=c["bg"])
        self.style.configure("TEntry",              fieldbackground=c["entry_bg"], foreground=c["fg"])
        self.style.configure("TScrollbar",          background=c["bg"], troughcolor=c["trough"])
        self.style.configure("Horizontal.TProgressbar",
                             background=c["progress_bar"], troughcolor=c["trough"])

        if self.dark_mode.get():
            self.style.configure("TButton",
                                 background="#3c3c3c", foreground=c["fg"], bordercolor="#555555")
            self.style.map("TButton",
                           background=[("active", "#5a5a5a"), ("disabled", "#2a2a2a")],
                           foreground=[("active", c["fg"]), ("disabled", "#666666")])
            self.style.map("TCheckbutton",
                           background=[("active", c["bg"])],
                           foreground=[("active", c["fg"])])
        else:
            self.style.map("TButton",     background=[], foreground=[])
            self.style.map("TCheckbutton", background=[], foreground=[])

        self.root.configure(bg=c["bg"])

        self.file_listbox.configure(
            bg=c["listbox_bg"],
            fg=c["listbox_fg"],
            selectbackground=c["select_bg"],
            selectforeground=c["select_fg"],
        )

        self.status_label.config(foreground=c["status_fg"])
        self.hint_label.config(foreground=c["hint_fg"])

        # Preserve correct colour on the ffmpeg badge
        txt = self.ffmpeg_status_label.cget("text")
        if "✅" in txt or "ready" in txt.lower():
            self.ffmpeg_status_label.config(foreground=c["ffmpeg_ok"])
        elif "⚠" in txt or "not found" in txt.lower():
            self.ffmpeg_status_label.config(foreground=c["ffmpeg_err"])

    # ------------------------------------------------------------------ #
    #  ffmpeg check                                                        #
    # ------------------------------------------------------------------ #

    def _check_ffmpeg(self):
        c = DARK_THEME if self.dark_mode.get() else LIGHT_THEME
        if self.converter.is_ffmpeg_available():
            self.ffmpeg_status_label.config(
                text="✅ ffmpeg ready", foreground=c["ffmpeg_ok"]
            )
        else:
            self.ffmpeg_status_label.config(
                text="⚠️ ffmpeg not found", foreground=c["ffmpeg_err"]
            )
            msg = "ffmpeg was not found on this system.\n\nPlease install ffmpeg:\n"
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
    #  Format change                                                       #
    # ------------------------------------------------------------------ #

    def _on_format_change(self, _event=None):
        fmt = self.format_var.get()
        self.convert_btn.config(text=f"▶  Convert to {fmt.upper()}")
        # WAV and FLAC are lossless — bitrate doesn't apply
        if fmt in ("wav", "flac"):
            self.bitrate_combo.config(state="disabled")
        else:
            self.bitrate_combo.config(state="readonly")

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
        self._add_paths(list(paths))

    def _on_drop(self, event):
        """Handle files dropped onto the listbox."""
        paths = _parse_dnd_paths(event.data)
        # Accept any file — validation happens inside the converter
        self._add_paths(paths)

    def _add_paths(self, paths: list[str]):
        added = 0
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self.file_listbox.insert(tk.END, p)
                added += 1
        if added:
            self._refresh_hint()
            self.status_label.config(text=f"{len(self.files)} file(s) queued")

    def _remove_selected(self):
        for idx in reversed(self.file_listbox.curselection()):
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
            messagebox.showwarning("No Output Directory", "Please choose an output directory.")
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

        threading.Thread(target=self._run_conversion, daemon=True).start()

    def _run_conversion(self):
        total = len(self.files)
        success_count = 0
        skipped_count = 0
        errors: list[str] = []
        log_entries: list[str] = []
        fmt = self.format_var.get()

        for i, input_path in enumerate(self.files):
            basename = os.path.basename(input_path)
            self._update_status(f"Converting {i + 1}/{total}: {basename}")

            out_dir = (
                os.path.dirname(input_path)
                if self.same_dir_var.get()
                else self.output_dir.get()
            )
            stem = os.path.splitext(basename)[0]
            output_path = os.path.join(out_dir, f"{stem}.{fmt}")

            if not self.overwrite_var.get() and os.path.exists(output_path):
                skipped_count += 1
                errors.append(f"SKIPPED  {basename}  →  output already exists")
                log_entries.append(f"SKIP: {input_path} → {output_path}")
                self._update_progress((i + 1) / total * 100)
                continue

            def _make_cb(file_idx: int):
                def cb(file_pct: float):
                    overall = (file_idx + file_pct / 100) / total * 100
                    self._update_progress(overall)
                return cb

            ok, error_msg = self.converter.convert(
                input_path,
                output_path,
                bitrate=self.bitrate_var.get(),
                fmt=fmt,
                progress_callback=_make_cb(i),
            )

            if ok:
                success_count += 1
                log_entries.append(f"SUCCESS: {input_path} → {output_path}")
            else:
                errors.append(f"ERROR    {basename}  →  {error_msg}")
                log_entries.append(f"FAIL: {input_path} | {error_msg}")

            self._update_progress((i + 1) / total * 100)

        self._write_log(log_entries)
        self._finish_conversion(success_count, skipped_count, errors, total, fmt)

    # ------------------------------------------------------------------ #
    #  Conversion history log                                              #
    # ------------------------------------------------------------------ #

    def _write_log(self, entries: list[str]):
        if not entries:
            return
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n--- Session {ts} ---\n")
                for entry in entries:
                    f.write(f"[{ts}] {entry}\n")
        except Exception:
            pass  # non-critical

    def _view_log(self):
        if not os.path.exists(self.LOG_FILE):
            messagebox.showinfo("No Log", "No conversion history found yet.")
            return

        c = DARK_THEME if self.dark_mode.get() else LIGHT_THEME

        win = tk.Toplevel(self.root)
        win.title("Conversion History")
        win.geometry("820x500")
        win.configure(bg=c["bg"])

        text_frame = ttk.Frame(win, padding=8)
        text_frame.pack(fill=tk.BOTH, expand=True)

        scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        log_font = (
            ("Courier New", 11) if sys.platform == "win32"
            else ("Menlo",      12) if sys.platform == "darwin"
            else ("Monospace",  11)
        )
        text = tk.Text(
            text_frame,
            wrap=tk.NONE,
            bg=c["listbox_bg"],
            fg=c["listbox_fg"],
            font=log_font,
            yscrollcommand=scroll.set,
        )
        scroll.config(command=text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        try:
            with open(self.LOG_FILE, "r", encoding="utf-8") as f:
                text.insert(tk.END, f.read())
        except Exception as e:
            text.insert(tk.END, f"Error reading log: {e}")

        text.config(state=tk.DISABLED)
        text.see(tk.END)

        btn_row = ttk.Frame(win, padding=(0, 4, 0, 8))
        btn_row.pack()
        ttk.Button(btn_row, text="Close", command=win.destroy, width=12).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            btn_row,
            text="Clear Log",
            command=lambda: self._clear_log(win),
            width=12,
        ).pack(side=tk.LEFT, padx=4)

    def _clear_log(self, parent_window=None):
        if not messagebox.askyesno("Clear Log", "Delete all conversion history?"):
            return
        try:
            os.remove(self.LOG_FILE)
        except FileNotFoundError:
            pass
        if parent_window:
            parent_window.destroy()
        messagebox.showinfo("Log Cleared", "Conversion history has been deleted.")

    # ------------------------------------------------------------------ #
    #  Thread-safe UI helpers                                              #
    # ------------------------------------------------------------------ #

    def _update_status(self, msg: str):
        self.root.after(0, lambda: self.status_label.config(text=msg))

    def _update_progress(self, value: float):
        self.root.after(0, lambda: self.progress_var.set(value))

    def _finish_conversion(
        self, success: int, skipped: int, errors: list, total: int, fmt: str
    ):
        def _do():
            self.is_converting = False
            self.convert_btn.config(state=tk.NORMAL, text=f"▶  Convert to {fmt.upper()}")
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
                    f"✅  Successfully converted {success} file(s) to {fmt.upper()}.",
                )

            self.status_label.config(
                text=f"Done — {success} converted, {skipped} skipped, {failed} failed"
            )

        self.root.after(0, _do)


# ------------------------------------------------------------------ #
#  Entry point                                                         #
# ------------------------------------------------------------------ #

def main():
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    # Windows: tell Windows this is a DPI-aware application
    if sys.platform == "win32":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    VideoToAudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
