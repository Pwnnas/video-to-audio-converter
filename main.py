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
#  Fonts (resolved once, used everywhere)                              #
# ------------------------------------------------------------------ #

def _pick(win, mac, lin):
    if sys.platform == "win32":   return win
    if sys.platform == "darwin":  return mac
    return lin

UI_FONT       = _pick("Segoe UI",    "SF Pro Text",    "Helvetica")
MONO_FONT     = _pick("Courier New", "Menlo",          "Monospace")
DISPLAY_FONT  = _pick("Segoe UI",    "SF Pro Display", "Helvetica")


# ------------------------------------------------------------------ #
#  Colour palettes                                                     #
# ------------------------------------------------------------------ #

LIGHT = {
    # chrome
    "header_bg":    "#1558d6",
    "header_fg":    "#ffffff",
    "header_sub":   "#c2d7ff",
    # page
    "bg":           "#f0f2f5",
    "card_bg":      "#ffffff",
    "border":       "#dde1e7",
    # text
    "fg":           "#1a1a1a",
    "muted":        "#5f6368",
    "hint":         "#9aa0a6",
    # widgets
    "listbox_bg":   "#ffffff",
    "listbox_fg":   "#1a1a1a",
    "entry_bg":     "#ffffff",
    "select_bg":    "#1558d6",
    "select_fg":    "#ffffff",
    # progress / accent
    "accent":       "#1558d6",
    "trough":       "#e0e3e8",
    # feedback
    "ok":           "#188038",
    "err":          "#c5221f",
    # primary button
    "btn_bg":       "#1558d6",
    "btn_fg":       "#ffffff",
    "btn_active":   "#1148b8",
    "btn_dis_bg":   "#c5ccd8",
    "btn_dis_fg":   "#ffffff",
}

DARK = {
    "header_bg":    "#111827",
    "header_fg":    "#f1f5f9",
    "header_sub":   "#6b7280",
    "bg":           "#1c1c1e",
    "card_bg":      "#2c2c2e",
    "border":       "#3a3a3c",
    "fg":           "#e5e7eb",
    "muted":        "#9ca3af",
    "hint":         "#4b5563",
    "listbox_bg":   "#2c2c2e",
    "listbox_fg":   "#e5e7eb",
    "entry_bg":     "#3a3a3c",
    "select_bg":    "#3b82f6",
    "select_fg":    "#ffffff",
    "accent":       "#3b82f6",
    "trough":       "#3a3a3c",
    "ok":           "#4ade80",
    "err":          "#f87171",
    "btn_bg":       "#3b82f6",
    "btn_fg":       "#ffffff",
    "btn_active":   "#2563eb",
    "btn_dis_bg":   "#374151",
    "btn_dis_fg":   "#6b7280",
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
        self.root.geometry("1060x880")
        self.root.resizable(True, True)
        self.root.minsize(820, 680)

        if sys.platform == "darwin":
            self._platform_theme = "aqua"
        elif sys.platform == "win32":
            self._platform_theme = "vista"
        else:
            self._platform_theme = "clam"

        self.style = ttk.Style()
        self.style.theme_use(self._platform_theme)

        self.converter = VideoConverter()
        self.files: list[str] = []
        self.output_dir = tk.StringVar()
        self.is_converting = False
        self.dark_mode = tk.BooleanVar(value=True)

        # Widgets that need colour updates on theme switch
        self._header_widgets: list[tk.Widget] = []
        self._card_frames:    list[tk.Widget] = []

        self.root.after(200, self._check_ffmpeg)
        self._build_ui()
        self._apply_theme()

    # ------------------------------------------------------------------ #
    #  UI helpers                                                          #
    # ------------------------------------------------------------------ #

    def _c(self) -> dict:
        return DARK if self.dark_mode.get() else LIGHT

    def _label_font(self, size=13, bold=False):
        weight = "bold" if bold else "normal"
        return (UI_FONT, size, weight)

    def _card(self, parent, title: str, expand=False, pady=(6, 0)):
        """A labelled white-card section."""
        c = self._c()
        outer = tk.Frame(parent, bg=c["border"], padx=1, pady=1)
        outer.pack(fill=tk.BOTH, expand=expand, padx=14, pady=pady)

        inner = tk.Frame(outer, bg=c["card_bg"])
        inner.pack(fill=tk.BOTH, expand=True)

        # Section title row
        title_row = tk.Frame(inner, bg=c["card_bg"])
        title_row.pack(fill=tk.X, padx=16, pady=(14, 6))
        lbl = tk.Label(title_row, text=title, bg=c["card_bg"], fg=c["muted"],
                       font=(UI_FONT, 12, "bold"))
        lbl.pack(side=tk.LEFT)

        # Content frame
        body = tk.Frame(inner, bg=c["card_bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 14))

        self._card_frames.extend([outer, inner, title_row, lbl, body])
        return body, outer, lbl

    # ------------------------------------------------------------------ #
    #  UI construction                                                     #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        c = DARK  # start with dark (matches default dark_mode=True)

        # ── Header banner ─────────────────────────────────────────────── #
        self.header_frame = tk.Frame(self.root, bg=c["header_bg"], pady=0)
        self.header_frame.pack(fill=tk.X)

        # Left: icon + title + subtitle
        left_hdr = tk.Frame(self.header_frame, bg=c["header_bg"])
        left_hdr.pack(side=tk.LEFT, padx=(22, 0), pady=20)

        self.header_title = tk.Label(
            left_hdr,
            text="🎬  Video to Audio Converter",
            bg=c["header_bg"], fg=c["header_fg"],
            font=(DISPLAY_FONT, 22, "bold"),
        )
        self.header_title.pack(anchor=tk.W)

        self.header_sub = tk.Label(
            left_hdr,
            text="Extract audio from any video file",
            bg=c["header_bg"], fg=c["header_sub"],
            font=(UI_FONT, 13),
        )
        self.header_sub.pack(anchor=tk.W, pady=(2, 0))

        # Right: dark mode toggle + ffmpeg badge
        right_hdr = tk.Frame(self.header_frame, bg=c["header_bg"])
        right_hdr.pack(side=tk.RIGHT, padx=(0, 22))

        self.dark_toggle = tk.Button(
            right_hdr,
            text="🌙  Dark",
            command=self._toggle_dark,
            bg=c["header_bg"], fg=c["header_fg"],
            activebackground=c["header_bg"], activeforeground=c["header_fg"],
            relief=tk.FLAT, bd=0, cursor="hand2",
            font=(UI_FONT, 13),
            padx=12, pady=8,
        )
        self.dark_toggle.pack(side=tk.LEFT, padx=(0, 10))

        self.ffmpeg_status_label = tk.Label(
            right_hdr, text="",
            bg=c["header_bg"], fg=c["header_sub"],
            font=(UI_FONT, 13),
        )
        self.ffmpeg_status_label.pack(side=tk.LEFT)

        self._header_widgets = [
            self.header_frame, left_hdr, right_hdr,
            self.header_title, self.header_sub,
            self.dark_toggle, self.ffmpeg_status_label,
        ]

        # ── Page body ─────────────────────────────────────────────────── #
        self.body = tk.Frame(self.root, bg=c["bg"])
        self.body.pack(fill=tk.BOTH, expand=True)

        # ── File list card ────────────────────────────────────────────── #
        list_body, list_outer, list_title = self._card(
            self.body, "VIDEO FILES", expand=True, pady=(12, 0)
        )

        # Listbox + scrollbars
        lb_frame = tk.Frame(list_body, bg=c["card_bg"])
        lb_frame.pack(fill=tk.BOTH, expand=True)

        scroll_y = ttk.Scrollbar(lb_frame, orient=tk.VERTICAL)
        scroll_x = ttk.Scrollbar(lb_frame, orient=tk.HORIZONTAL)

        self.file_listbox = tk.Listbox(
            lb_frame,
            selectmode=tk.EXTENDED,
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
            activestyle="none",
            font=(MONO_FONT, 13),
            bg=c["listbox_bg"], fg=c["listbox_fg"],
            selectbackground=c["select_bg"], selectforeground=c["select_fg"],
            bd=0, highlightthickness=0,
            relief=tk.FLAT,
        )
        scroll_y.config(command=self.file_listbox.yview)
        scroll_x.config(command=self.file_listbox.xview)

        scroll_y.pack(side=tk.RIGHT,  fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._card_frames.append(lb_frame)

        if HAS_DND:
            self.file_listbox.drop_target_register(DND_FILES)
            self.file_listbox.dnd_bind("<<Drop>>", self._on_drop)

        hint_text = (
            "Drop files here  ·  or click  ➕ Add Files  below" if HAS_DND
            else "Click  ➕ Add Files  below to get started"
        )
        self.hint_label = tk.Label(
            lb_frame,
            text=hint_text,
            bg=c["card_bg"], fg=c["hint"],
            font=(UI_FONT, 14, "italic"),
        )
        self.hint_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        self._card_frames.append(self.hint_label)

        # ── File-action toolbar ───────────────────────────────────────── #
        toolbar = tk.Frame(self.body, bg=c["bg"])
        toolbar.pack(fill=tk.X, padx=14, pady=(8, 0))
        self._card_frames.append(toolbar)

        btn_style = dict(
            relief=tk.FLAT, bd=0, cursor="hand2",
            font=(UI_FONT, 13), padx=16, pady=8,
        )
        self._toolbar_btns: list[tk.Button] = []
        for text, cmd in [
            ("➕  Add Files",       self._add_files),
            ("🗑  Remove Selected", self._remove_selected),
            ("✖  Clear All",        self._clear_all),
        ]:
            b = tk.Button(toolbar, text=text, command=cmd, **btn_style)
            b.pack(side=tk.LEFT, padx=(0, 6))
            self._toolbar_btns.append(b)

        # ── Output directory card ──────────────────────────────────────── #
        out_body, _, _ = self._card(self.body, "OUTPUT DIRECTORY", pady=(8, 0))

        out_row = tk.Frame(out_body, bg=c["card_bg"])
        out_row.pack(fill=tk.X, pady=(0, 6))
        self._card_frames.append(out_row)

        self.out_entry = ttk.Entry(
            out_row,
            textvariable=self.output_dir,
            state="readonly",
            font=(UI_FONT, 13),
        )
        self.out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        browse_btn = tk.Button(
            out_row, text="📂  Browse", command=self._browse_output,
            relief=tk.FLAT, bd=0, cursor="hand2",
            font=(UI_FONT, 13), padx=16, pady=7,
        )
        browse_btn.pack(side=tk.LEFT)
        self._toolbar_btns.append(browse_btn)

        self.same_dir_var = tk.BooleanVar(value=True)
        self.same_dir_chk = ttk.Checkbutton(
            out_body,
            text="Save next to original files",
            variable=self.same_dir_var,
            command=self._toggle_output_dir,
        )
        self.same_dir_chk.pack(anchor=tk.W)
        self._toggle_output_dir()

        # ── Options card ───────────────────────────────────────────────── #
        opt_body, _, _ = self._card(self.body, "OPTIONS", pady=(8, 0))
        opt_row = tk.Frame(opt_body, bg=c["card_bg"])
        opt_row.pack(fill=tk.X)
        self._card_frames.append(opt_row)

        def _opt_label(text):
            l = tk.Label(opt_row, text=text, bg=c["card_bg"], fg=c["fg"],
                         font=(UI_FONT, 13))
            l.pack(side=tk.LEFT)
            self._card_frames.append(l)
            return l

        _opt_label("Format")
        self.format_var = tk.StringVar(value="m4a")
        self.format_combo = ttk.Combobox(
            opt_row, textvariable=self.format_var,
            values=VideoConverter.SUPPORTED_FORMATS,
            state="readonly", width=8,
            font=(UI_FONT, 13),
        )
        self.format_combo.pack(side=tk.LEFT, padx=(8, 24))
        self.format_combo.bind("<<ComboboxSelected>>", self._on_format_change)

        _opt_label("Bitrate")
        self.bitrate_var = tk.StringVar(value="192k")
        self.bitrate_combo = ttk.Combobox(
            opt_row, textvariable=self.bitrate_var,
            values=["64k", "96k", "128k", "160k", "192k", "256k", "320k"],
            state="readonly", width=8,
            font=(UI_FONT, 13),
        )
        self.bitrate_combo.pack(side=tk.LEFT, padx=(8, 24))

        self.overwrite_var = tk.BooleanVar(value=False)
        self.overwrite_chk = ttk.Checkbutton(
            opt_row, text="Overwrite existing files",
            variable=self.overwrite_var,
        )
        self.overwrite_chk.pack(side=tk.LEFT)

        # ── Progress card ──────────────────────────────────────────────── #
        prog_body, _, _ = self._card(self.body, "PROGRESS", pady=(8, 0))

        self.style.configure(
            "Accent.Horizontal.TProgressbar",
            thickness=14,
            background=c["accent"],
            troughcolor=c["trough"],
        )
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            prog_body,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
            style="Accent.Horizontal.TProgressbar",
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 6))

        status_row = tk.Frame(prog_body, bg=c["card_bg"])
        status_row.pack(fill=tk.X)
        self._card_frames.append(status_row)

        self.status_label = tk.Label(
            status_row, text="Ready",
            bg=c["card_bg"], fg=c["muted"],
            font=(UI_FONT, 13),
        )
        self.status_label.pack(side=tk.LEFT)

        self.pct_label = tk.Label(
            status_row, text="",
            bg=c["card_bg"], fg=c["accent"],
            font=(UI_FONT, 13, "bold"),
        )
        self.pct_label.pack(side=tk.RIGHT)
        self._card_frames.extend([self.status_label, self.pct_label])

        # ── Bottom action bar ──────────────────────────────────────────── #
        action_bar = tk.Frame(self.body, bg=c["bg"])
        action_bar.pack(fill=tk.X, padx=14, pady=(10, 16))
        self._card_frames.append(action_bar)

        # Secondary: View Log
        log_btn = tk.Button(
            action_bar, text="📋  View Log",
            command=self._view_log,
            relief=tk.FLAT, bd=0, cursor="hand2",
            font=(UI_FONT, 13), padx=18, pady=10,
        )
        log_btn.pack(side=tk.LEFT)
        self._toolbar_btns.append(log_btn)

        # Primary: Convert
        self.convert_btn = tk.Button(
            action_bar,
            text="▶  Convert to M4A",
            command=self._start_conversion,
            bg=c["btn_bg"], fg=c["btn_fg"],
            activebackground=c["btn_active"], activeforeground=c["btn_fg"],
            relief=tk.FLAT, bd=0, cursor="hand2",
            font=(UI_FONT, 15, "bold"),
            padx=36, pady=12,
        )
        self.convert_btn.pack(side=tk.RIGHT)

    # ------------------------------------------------------------------ #
    #  Theme                                                               #
    # ------------------------------------------------------------------ #

    def _toggle_dark(self):
        self.dark_mode.set(not self.dark_mode.get())
        self._apply_theme()

    def _apply_theme(self):
        c = self._c()
        is_dark = self.dark_mode.get()

        # Update dark toggle label
        self.dark_toggle.config(text="☀️  Light" if is_dark else "🌙  Dark")

        # ttk theme
        self.style.theme_use("clam" if is_dark else self._platform_theme)

        # ttk style overrides
        self.style.configure(".",
            background=c["card_bg"], foreground=c["fg"])
        self.style.configure("TFrame",     background=c["card_bg"])
        self.style.configure("TLabel",     background=c["card_bg"], foreground=c["fg"])
        self.style.configure("TCheckbutton", background=c["card_bg"], foreground=c["fg"])
        self.style.configure("TCombobox",
            fieldbackground=c["entry_bg"], foreground=c["fg"], background=c["card_bg"])
        self.style.configure("TEntry",
            fieldbackground=c["entry_bg"], foreground=c["fg"])
        self.style.configure("TScrollbar",
            background=c["card_bg"], troughcolor=c["trough"], arrowcolor=c["muted"])
        self.style.configure("Accent.Horizontal.TProgressbar",
            background=c["accent"], troughcolor=c["trough"], thickness=10)

        if is_dark:
            self.style.map("TCheckbutton",
                background=[("active", c["card_bg"])],
                foreground=[("active", c["fg"])])
            self.style.map("TCombobox",
                fieldbackground=[("readonly", c["entry_bg"])],
                foreground=[("readonly", c["fg"])])

        # Root + body
        self.root.configure(bg=c["bg"])
        self.body.configure(bg=c["bg"])

        # Header
        for w in self._header_widgets:
            w.configure(bg=c["header_bg"])
        self.header_title.configure(fg=c["header_fg"])
        self.header_sub.configure(fg=c["header_sub"])
        self.dark_toggle.configure(
            fg=c["header_fg"],
            activebackground=c["header_bg"], activeforeground=c["header_fg"],
        )
        # Re-apply ffmpeg badge colour
        txt = self.ffmpeg_status_label.cget("text")
        if "✅" in txt:
            self.ffmpeg_status_label.configure(fg=c["ok"])
        elif "⚠" in txt:
            self.ffmpeg_status_label.configure(fg=c["err"])
        else:
            self.ffmpeg_status_label.configure(fg=c["header_sub"])

        # Card frames / labels
        for w in self._card_frames:
            try:
                w.configure(bg=c["card_bg"])
                if isinstance(w, tk.Label):
                    # hint and status labels keep their own fg, set below
                    pass
            except tk.TclError:
                pass

        # Specific label foregrounds
        self.hint_label.configure(fg=c["hint"])
        self.status_label.configure(fg=c["muted"])
        self.pct_label.configure(fg=c["accent"])

        # Toolbar / secondary buttons
        for btn in self._toolbar_btns:
            btn.configure(
                bg=c["card_bg"], fg=c["fg"],
                activebackground=c["border"], activeforeground=c["fg"],
            )

        # Convert button (primary — keeps its own colour)
        if self.is_converting:
            self.convert_btn.configure(
                bg=c["btn_dis_bg"], fg=c["btn_dis_fg"],
                activebackground=c["btn_dis_bg"],
            )
        else:
            self.convert_btn.configure(
                bg=c["btn_bg"], fg=c["btn_fg"],
                activebackground=c["btn_active"], activeforeground=c["btn_fg"],
            )

        # Listbox
        self.file_listbox.configure(
            bg=c["listbox_bg"], fg=c["listbox_fg"],
            selectbackground=c["select_bg"], selectforeground=c["select_fg"],
        )

    # ------------------------------------------------------------------ #
    #  ffmpeg check                                                        #
    # ------------------------------------------------------------------ #

    def _check_ffmpeg(self):
        c = self._c()
        if self.converter.is_ffmpeg_available():
            self.ffmpeg_status_label.configure(text="✅ ffmpeg ready", fg=c["ok"])
        else:
            self.ffmpeg_status_label.configure(text="⚠️ ffmpeg not found", fg=c["err"])
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
        self.convert_btn.configure(text=f"▶  Convert to {fmt.upper()}")
        if fmt in ("wav", "flac"):
            self.bitrate_combo.configure(state="disabled")
        else:
            self.bitrate_combo.configure(state="readonly")

    # ------------------------------------------------------------------ #
    #  File-list callbacks                                                 #
    # ------------------------------------------------------------------ #

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select Video Files",
            filetypes=[
                ("Video files",
                 "*.mp4 *.mov *.avi *.mkv *.wmv *.flv *.webm *.m4v "
                 "*.mpeg *.mpg *.ts *.3gp"),
                ("All files", "*.*"),
            ],
        )
        self._add_paths(list(paths))

    def _on_drop(self, event):
        self._add_paths(_parse_dnd_paths(event.data))

    def _add_paths(self, paths: list[str]):
        added = 0
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self.file_listbox.insert(tk.END, p)
                added += 1
        if added:
            self._refresh_hint()
            self.status_label.configure(text=f"{len(self.files)} file(s) queued")

    def _remove_selected(self):
        for idx in reversed(self.file_listbox.curselection()):
            self.file_listbox.delete(idx)
            del self.files[idx]
        self._refresh_hint()

    def _clear_all(self):
        self.file_listbox.delete(0, tk.END)
        self.files.clear()
        self._refresh_hint()
        self.status_label.configure(text="Ready")
        self.pct_label.configure(text="")
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
        self.out_entry.configure(
            state="disabled" if self.same_dir_var.get() else "readonly"
        )

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

        c = self._c()
        self.is_converting = True
        self.convert_btn.configure(
            state=tk.DISABLED, text="⏳  Converting…",
            bg=c["btn_dis_bg"], fg=c["btn_dis_fg"],
            activebackground=c["btn_dis_bg"],
        )
        self.progress_var.set(0)
        self.pct_label.configure(text="0%")

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
                os.path.dirname(input_path) if self.same_dir_var.get()
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
                input_path, output_path,
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
            pass

    def _view_log(self):
        if not os.path.exists(self.LOG_FILE):
            messagebox.showinfo("No Log", "No conversion history found yet.")
            return

        c = self._c()
        win = tk.Toplevel(self.root)
        win.title("Conversion History")
        win.geometry("820x500")
        win.configure(bg=c["bg"])

        text_frame = tk.Frame(win, bg=c["bg"], padx=12, pady=12)
        text_frame.pack(fill=tk.BOTH, expand=True)

        scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        text = tk.Text(
            text_frame,
            wrap=tk.NONE,
            bg=c["listbox_bg"], fg=c["listbox_fg"],
            font=(MONO_FONT, 11),
            relief=tk.FLAT, bd=0,
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

        text.configure(state=tk.DISABLED)
        text.see(tk.END)

        btn_row = tk.Frame(win, bg=c["bg"], pady=8)
        btn_row.pack()
        for lbl, cmd in [
            ("Close",     win.destroy),
            ("Clear Log", lambda: self._clear_log(win)),
        ]:
            tk.Button(
                btn_row, text=lbl, command=cmd,
                bg=c["card_bg"], fg=c["fg"],
                activebackground=c["border"], activeforeground=c["fg"],
                relief=tk.FLAT, bd=0, cursor="hand2",
                font=(UI_FONT, 12), padx=16, pady=6,
            ).pack(side=tk.LEFT, padx=6)

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
        self.root.after(0, lambda: self.status_label.configure(text=msg))

    def _update_progress(self, value: float):
        def _do():
            self.progress_var.set(value)
            self.pct_label.configure(text=f"{int(value)}%")
        self.root.after(0, _do)

    def _finish_conversion(
        self, success: int, skipped: int, errors: list, total: int, fmt: str
    ):
        def _do():
            c = self._c()
            self.is_converting = False
            self.convert_btn.configure(
                state=tk.NORMAL,
                text=f"▶  Convert to {fmt.upper()}",
                bg=c["btn_bg"], fg=c["btn_fg"],
                activebackground=c["btn_active"], activeforeground=c["btn_fg"],
            )
            self.progress_var.set(100)
            self.pct_label.configure(text="100%")

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

            self.status_label.configure(
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
