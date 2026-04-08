import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import yt_dlp
import os
import glob
import shutil
import re


class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTubeMate Downloader")
        self.root.geometry("780x640")
        self.root.resizable(True, True)
        self.root.configure(bg="#F7F9FB")
        self.app_dir = os.path.dirname(os.path.abspath(__file__))

        self.formats = []
        self.output_folder = os.getcwd()
        self.node_path = None
        self.js_runtime_name = None
        self.js_runtime_path = None
        self.ffmpeg_path = None
        self.ffmpeg_location = None
        self.progress_value = tk.DoubleVar(master=self.root, value=0.0)
        self.eta_value = tk.StringVar(master=self.root, value="ETA: --")
        self.progress_text = tk.StringVar(master=self.root, value="0%")
        self.speed_value = tk.StringVar(master=self.root, value="Speed: --")
        self.warning_value = tk.StringVar(master=self.root, value="")
        self.format_placeholder = "Fetch formats to choose a quality"

        self.detect_dependencies()

        self.configure_styles()
        self.create_widgets()
        self.center_window()

    def configure_styles(self):
        self.colors = {
            "bg": "#F7F9FB",
            "card": "#FFFFFF",
            "primary": "#4A6FA5",
            "primary_hover": "#3F618F",
            "text": "#2E2E2E",
            "secondary_text": "#6B7280",
            "border": "#E5E7EB",
            "success": "#4CAF50",
            "error": "#E57373",
            "button_surface": "#EEF2F6",
            "button_hover": "#E3E8EF",
        }

        self.fonts = {
            "title": ("Segoe UI", 18, "bold"),
            "subtitle": ("Segoe UI", 10),
            "section": ("Segoe UI Semibold", 10),
            "label": ("Segoe UI", 10),
            "input": ("Segoe UI", 10),
            "button": ("Segoe UI Semibold", 10),
            "status": ("Segoe UI", 10),
        }

        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background=self.colors["bg"], foreground=self.colors["text"], font=self.fonts["label"])
        style.configure("App.TFrame", background=self.colors["bg"])
        style.configure(
            "Card.TFrame",
            background=self.colors["card"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            borderwidth=1,
            relief="solid",
        )
        style.configure("Header.TLabel", background=self.colors["bg"], foreground=self.colors["text"], font=self.fonts["title"])
        style.configure("Subheader.TLabel", background=self.colors["bg"], foreground=self.colors["secondary_text"], font=self.fonts["subtitle"])
        style.configure("CardTitle.TLabel", background=self.colors["card"], foreground=self.colors["text"], font=self.fonts["section"])
        style.configure("Body.TLabel", background=self.colors["card"], foreground=self.colors["text"], font=self.fonts["label"])
        style.configure(
            "Muted.TLabel",
            background=self.colors["card"],
            foreground=self.colors["secondary_text"],
            font=self.fonts["label"],
        )
        style.configure(
            "Status.TLabel",
            background=self.colors["card"],
            foreground=self.colors["secondary_text"],
            font=self.fonts["status"],
        )
        style.configure(
            "StatusSuccess.TLabel",
            background=self.colors["card"],
            foreground=self.colors["success"],
            font=self.fonts["status"],
        )
        style.configure(
            "StatusError.TLabel",
            background=self.colors["card"],
            foreground=self.colors["error"],
            font=self.fonts["status"],
        )
        style.configure(
            "Eta.TLabel",
            background=self.colors["card"],
            foreground=self.colors["secondary_text"],
            font=("Segoe UI", 9),
        )
        style.configure(
            "ProgressMeta.TLabel",
            background=self.colors["card"],
            foreground=self.colors["secondary_text"],
            font=("Segoe UI", 9),
        )
        style.configure(
            "ProgressValue.TLabel",
            background=self.colors["card"],
            foreground=self.colors["text"],
            font=("Segoe UI Semibold", 9),
        )
        style.configure(
            "Warning.TLabel",
            background=self.colors["card"],
            foreground=self.colors["secondary_text"],
            font=("Segoe UI", 9),
        )

        style.configure(
            "Modern.TEntry",
            fieldbackground=self.colors["card"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            padding=(10, 8),
            relief="solid",
            borderwidth=1,
        )
        style.map(
            "Modern.TEntry",
            bordercolor=[("focus", self.colors["primary"])],
            lightcolor=[("focus", self.colors["primary"])],
            darkcolor=[("focus", self.colors["primary"])],
        )

        style.configure(
            "Modern.TCombobox",
            fieldbackground=self.colors["card"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            padding=(10, 8),
            arrowsize=14,
            relief="solid",
            borderwidth=1,
        )
        style.map(
            "Modern.TCombobox",
            fieldbackground=[("readonly", self.colors["card"])],
            selectbackground=[("readonly", self.colors["card"])],
            selectforeground=[("readonly", self.colors["text"])],
            bordercolor=[("focus", self.colors["primary"])],
            lightcolor=[("focus", self.colors["primary"])],
            darkcolor=[("focus", self.colors["primary"])],
        )

        style.configure(
            "Primary.TButton",
            font=self.fonts["button"],
            background=self.colors["primary"],
            foreground="#FFFFFF",
            borderwidth=0,
            focusthickness=0,
            padding=(16, 10),
            relief="flat",
        )
        style.map(
            "Primary.TButton",
            background=[
                ("active", self.colors["primary_hover"]),
                ("pressed", self.colors["primary_hover"]),
                ("disabled", self.colors["border"]),
            ],
            foreground=[("disabled", "#FFFFFF")],
        )

        style.configure(
            "Secondary.TButton",
            font=self.fonts["button"],
            background=self.colors["button_surface"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["button_surface"],
            darkcolor=self.colors["button_surface"],
            padding=(14, 10),
            relief="solid",
            borderwidth=1,
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("active", self.colors["button_hover"]),
                ("pressed", self.colors["button_hover"]),
                ("disabled", self.colors["bg"]),
            ],
            foreground=[("disabled", self.colors["secondary_text"])],
        )
        style.configure(
            "Modern.Horizontal.TProgressbar",
            troughcolor=self.colors["button_surface"],
            background=self.colors["primary"],
            darkcolor=self.colors["primary"],
            lightcolor=self.colors["primary"],
            bordercolor=self.colors["border"],
            thickness=12,
        )

    def center_window(self):
        self.root.update_idletasks()
        width = max(780, self.root.winfo_reqwidth())
        height = max(640, self.root.winfo_reqheight())
        self.root.minsize(760, 620)
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def find_executable(self, executable_name):
        path = shutil.which(executable_name)
        if path:
            return os.path.normpath(path)

        local_app_data = os.environ.get("LOCALAPPDATA", "")
        common_directories = [
            os.path.join(self.app_dir, "tools", "ffmpeg", "bin"),
            os.path.join(self.app_dir, "ffmpeg", "bin"),
            os.path.join(local_app_data, "Microsoft", "WinGet", "Links"),
            os.path.join(os.environ.get("ProgramFiles", ""), "nodejs"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "nodejs"),
            os.path.join(os.environ.get("ProgramFiles", ""), "ffmpeg", "bin"),
            os.path.join(os.environ.get("ProgramFiles", ""), "FFmpeg", "bin"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "ffmpeg", "bin"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "FFmpeg", "bin"),
            os.path.join("C:\\", "ffmpeg", "bin"),
            os.path.join("C:\\", "FFmpeg", "bin"),
        ]

        for directory in common_directories:
            candidate = os.path.join(directory, f"{executable_name}.exe")
            if os.path.isfile(candidate):
                return os.path.normpath(candidate)

        package_patterns = [
            os.path.join(self.app_dir, "tools", "ffmpeg", "*", "bin", f"{executable_name}.exe"),
            os.path.join(local_app_data, "Microsoft", "WinGet", "Packages", f"*{executable_name}*", "*", f"{executable_name}.exe"),
            os.path.join(local_app_data, "Microsoft", "WinGet", "Packages", "*FFmpeg*", "*", "bin", f"{executable_name}.exe"),
        ]

        for pattern in package_patterns:
            for candidate in glob.glob(pattern):
                if os.path.isfile(candidate):
                    return os.path.normpath(candidate)

        return None

    def detect_dependencies(self):
        self.node_path = None
        self.js_runtime_name = None
        self.js_runtime_path = None
        self.ffmpeg_path = None
        self.ffmpeg_location = None

        self.node_path = self.find_executable("node")
        deno_path = self.find_executable("deno")
        self.ffmpeg_path = self.find_executable("ffmpeg")

        if self.node_path:
            self.js_runtime_name = "node"
            self.js_runtime_path = self.node_path
        elif deno_path:
            self.js_runtime_name = "deno"
            self.js_runtime_path = deno_path

        if self.ffmpeg_path:
            self.ffmpeg_location = os.path.dirname(self.ffmpeg_path)

    def build_ydl_opts(self):
        ydl_opts = {
            'quiet': True,
            'socket_timeout': 30,
            'extractor_retries': 5,
            'logger': self.YTDLPLogger(self),
        }

        if self.js_runtime_name and self.js_runtime_path:
            ydl_opts['js_runtimes'] = {
                self.js_runtime_name: {
                    'path': self.js_runtime_path,
                }
            }
            ydl_opts['remote_components'] = ['ejs:github']

        if self.ffmpeg_location:
            ydl_opts['ffmpeg_location'] = self.ffmpeg_location

        return ydl_opts

    class YTDLPLogger:
        def __init__(self, app):
            self.app = app

        def debug(self, msg):
            return

        def warning(self, msg):
            self.app.handle_ydlp_warning(msg)

        def error(self, msg):
            self.app.handle_ydlp_warning(msg)

    def get_format_candidates(self, info):
        formats = info.get('formats', [])
        merge_candidates = [
            f for f in formats
            if f.get('format_id')
            and f.get('vcodec') != 'none'
            and f.get('acodec') == 'none'
            and f.get('height', 0) >= 720
        ]

        if not merge_candidates:
            merge_candidates = [
                f for f in formats
                if f.get('format_id')
                and f.get('vcodec') != 'none'
                and f.get('acodec') == 'none'
            ]

        direct_candidates = [
            f for f in formats
            if f.get('format_id')
            and f.get('vcodec') != 'none'
            and f.get('acodec') != 'none'
        ]

        high_quality_direct_candidates = [f for f in direct_candidates if f.get('height', 0) >= 720]
        if high_quality_direct_candidates:
            direct_candidates = high_quality_direct_candidates

        merge_candidates = sorted(
            merge_candidates,
            key=lambda f: (
                f.get('height', 0),
                f.get('fps', 0),
                f.get('tbr', 0) or 0,
                f.get('filesize') or f.get('filesize_approx') or 0,
            ),
            reverse=True,
        )
        direct_candidates = sorted(
            direct_candidates,
            key=lambda f: (
                f.get('height', 0),
                f.get('fps', 0),
                f.get('tbr', 0) or 0,
                f.get('filesize') or f.get('filesize_approx') or 0,
            ),
            reverse=True,
        )

        candidates = []
        seen_format_ids = set()

        for format_info in merge_candidates:
            candidates.append((format_info, True))
            seen_format_ids.add(format_info['format_id'])

        for format_info in direct_candidates:
            if format_info['format_id'] not in seen_format_ids:
                candidates.append((format_info, False))
                seen_format_ids.add(format_info['format_id'])

        return candidates

    def build_format_label(self, format_info, requires_merge):
        height = format_info.get('height', '?')
        ext = format_info.get('ext', 'unknown')
        if requires_merge:
            note = "Video only"
            if not self.ffmpeg_location:
                note = "Video only - needs FFmpeg"
        else:
            note = "Single file"
        return f"{format_info['format_id']} - {height}p - {ext} - {note}"

    def ensure_js_runtime(self):
        if self.js_runtime_name and self.js_runtime_path:
            return True

        self.set_status("No supported JavaScript runtime found. Install Node.js or Deno to continue.")
        messagebox.showerror(
            "Runtime Required",
            "No supported JavaScript runtime was detected.\n\n"
            "Install Node.js or Deno, then reopen the app and try again."
        )
        return False

    def ensure_ffmpeg(self):
        if self.ffmpeg_path and self.ffmpeg_location:
            return True

        self.set_status("FFmpeg is required to merge video and audio streams.")
        messagebox.showerror(
            "FFmpeg Required",
            "FFmpeg was not found on this system.\n\n"
            "Install FFmpeg and reopen the app to enable video downloads."
        )
        return False

    def get_startup_status(self):
        if self.js_runtime_path and self.ffmpeg_location:
            return "Ready to fetch available formats."
        if self.js_runtime_path and not self.ffmpeg_location:
            return "Runtime detected. Some formats will require FFmpeg for merging."
        if not self.js_runtime_path and self.ffmpeg_location:
            return "FFmpeg detected. Install Node.js or Deno for reliable format extraction."
        return "Install Node.js or Deno plus FFmpeg to enable downloads."

    def create_widgets(self):
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        main_frame = ttk.Frame(self.root, style="App.TFrame", padding=16)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)

        header_frame = ttk.Frame(main_frame, style="App.TFrame")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header_frame.grid_columnconfigure(0, weight=1)

        title_label = ttk.Label(header_frame, text="YouTube Downloader", style="Header.TLabel")
        title_label.grid(row=0, column=0, sticky="w")

        subtitle_label = ttk.Label(
            header_frame,
            text="Download high-quality video formats with a simple, focused workflow.",
            style="Subheader.TLabel",
        )
        subtitle_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        content_card = ttk.Frame(main_frame, style="Card.TFrame", padding=14)
        content_card.grid(row=1, column=0, sticky="nsew")
        content_card.grid_columnconfigure(0, weight=0)
        content_card.grid_columnconfigure(1, weight=1)
        content_card.grid_columnconfigure(2, weight=0)

        ttk.Label(content_card, text="Download Details", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10)
        )

        ttk.Label(content_card, text="YouTube Video URL", style="Body.TLabel").grid(
            row=1, column=0, sticky="w", pady=(0, 4)
        )
        self.url_entry = ttk.Entry(content_card, width=60, style="Modern.TEntry")
        self.url_entry.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 10), ipady=3)

        ttk.Label(content_card, text="Output Folder", style="Body.TLabel").grid(
            row=3, column=0, sticky="w", pady=(0, 4)
        )
        self.folder_label = ttk.Label(
            content_card,
            text=self.output_folder,
            width=45,
            style="Muted.TLabel",
            anchor="w",
            wraplength=450,
            justify="left",
        )
        self.folder_label.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 10), padx=(0, 10))
        ttk.Button(
            content_card,
            text="Browse",
            command=self.select_output_folder,
            style="Secondary.TButton",
        ).grid(row=4, column=2, sticky="e", pady=(0, 10))

        self.fetch_btn = ttk.Button(
            content_card,
            text="Fetch Formats",
            command=self.fetch_formats,
            style="Secondary.TButton",
        )
        self.fetch_btn.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        ttk.Label(content_card, text="Available Formats", style="Body.TLabel").grid(
            row=6, column=0, sticky="w", pady=(0, 4)
        )
        self.format_combo = ttk.Combobox(content_card, state="readonly", width=57, style="Modern.TCombobox")
        self.format_combo.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(0, 10), ipady=3)
        self.format_combo.set(self.format_placeholder)

        self.download_btn = ttk.Button(
            content_card,
            text="Download",
            command=self.download_video,
            style="Primary.TButton",
        )
        self.download_btn.grid(row=8, column=0, columnspan=3, sticky="ew")

        status_card = ttk.Frame(content_card, style="Card.TFrame", padding=10)
        status_card.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        status_card.grid_columnconfigure(0, weight=1)

        ttk.Label(status_card, text="Status", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.status_label = ttk.Label(
            status_card,
            text="Ready to fetch available formats.",
            style="Status.TLabel",
            anchor="w",
            justify="left",
            wraplength=680,
        )
        self.status_label.grid(row=1, column=0, sticky="ew")

        self.warning_label = ttk.Label(
            status_card,
            textvariable=self.warning_value,
            style="Warning.TLabel",
            anchor="w",
            justify="left",
            wraplength=680,
        )
        self.warning_label.grid(row=2, column=0, sticky="ew", pady=(4, 0))

        progress_frame = ttk.Frame(status_card, style="Card.TFrame")
        progress_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        progress_frame.grid_columnconfigure(0, weight=1)
        progress_frame.grid_columnconfigure(1, weight=0)
        progress_frame.grid_columnconfigure(2, weight=0)

        ttk.Label(
            progress_frame,
            text="Download Progress",
            style="ProgressMeta.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.progress_percent_label = ttk.Label(
            progress_frame,
            textvariable=self.progress_text,
            style="ProgressValue.TLabel",
            anchor="e",
            width=6,
        )
        self.progress_percent_label.grid(row=0, column=1, sticky="e", padx=(10, 8), pady=(0, 4))

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            style="Modern.Horizontal.TProgressbar",
            mode="determinate",
            maximum=100,
            variable=self.progress_value,
            length=440,
        )
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

        meta_frame = ttk.Frame(status_card, style="Card.TFrame")
        meta_frame.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        meta_frame.grid_columnconfigure(0, weight=1)
        meta_frame.grid_columnconfigure(1, weight=1)

        self.speed_label = ttk.Label(
            meta_frame,
            textvariable=self.speed_value,
            style="Eta.TLabel",
            anchor="w",
        )
        self.speed_label.grid(row=0, column=0, sticky="w")

        self.eta_label = ttk.Label(
            meta_frame,
            textvariable=self.eta_value,
            style="Eta.TLabel",
            anchor="e",
        )
        self.eta_label.grid(row=0, column=1, sticky="e")

        self.url_entry.focus_set()
        self.set_status(self.get_startup_status())

    def set_status(self, text):
        text = self.clean_text(text)
        status_style = "Status.TLabel"
        normalized_text = text.lower()

        if any(keyword in normalized_text for keyword in ("failed", "error", "no high-quality formats")):
            status_style = "StatusError.TLabel"
        elif any(keyword in normalized_text for keyword in ("loaded", "finished", "complete", "ready")):
            status_style = "StatusSuccess.TLabel"

        self.run_on_ui_thread(self.status_label.config, text=text, style=status_style)

    def run_on_ui_thread(self, callback, *args, **kwargs):
        if threading.current_thread() is threading.main_thread():
            callback(*args, **kwargs)
        else:
            self.root.after(0, lambda: callback(*args, **kwargs))

    def clean_text(self, text):
        if text is None:
            return ""
        text = str(text)
        text = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)
        text = re.sub(r'[\r\n\t]+', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return ''.join(ch for ch in text if ch.isprintable())

    def clean_status_value(self, label, value, fallback):
        value = self.clean_text(value)
        if not value or value in {"N/A", "NA", "Unknown"}:
            return f"{label}: {fallback}"
        return f"{label}: {value}"

    def handle_ydlp_warning(self, message):
        message = self.clean_text(message)
        if not message:
            return
        lowered = message.lower()
        if "n challenge solving failed" in lowered or "error solving n challenge request" in lowered:
            message = "YouTube returned a slow challenge response. Some formats may be missing for this fetch. Try again if needed."
        elif message.startswith("WARNING:"):
            message = message.replace("WARNING:", "", 1).strip()
        self.run_on_ui_thread(self.warning_value.set, message[:220])

    def parse_percent(self, percent_text):
        match = re.search(r'(\d+(?:\.\d+)?)', percent_text or "")
        return float(match.group(1)) if match else 0.0

    def reset_progress(self, eta_text="ETA: --"):
        self.run_on_ui_thread(self.progress_value.set, 0.0)
        self.run_on_ui_thread(self.eta_value.set, self.clean_status_value("ETA", eta_text.replace("ETA:", "").strip(), "--"))
        self.run_on_ui_thread(self.speed_value.set, "Speed: --")
        self.run_on_ui_thread(self.progress_text.set, "0%")
        self.run_on_ui_thread(self.warning_value.set, "")

    def update_progress(self, percent_text="", eta_text="", speed_text=""):
        percent_text = self.clean_text(percent_text)
        eta_text = self.clean_text(eta_text)
        speed_text = self.clean_text(speed_text)
        percent_value = max(0.0, min(100.0, self.parse_percent(percent_text)))
        eta_display = self.clean_status_value("ETA", eta_text, "Estimating...")
        speed_display = self.clean_status_value("Speed", speed_text, "--")
        self.run_on_ui_thread(self.progress_value.set, percent_value)
        self.run_on_ui_thread(self.eta_value.set, eta_display)
        self.run_on_ui_thread(self.speed_value.set, speed_display)
        self.run_on_ui_thread(self.progress_text.set, f"{int(round(percent_value))}%")

    def select_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder = folder
            self.folder_label.config(text=folder)

    def set_format_placeholder(self, text=None):
        placeholder = text or self.format_placeholder
        self.run_on_ui_thread(self.format_combo.set, placeholder)

    def update_format_combo(self, values, select_first=False):
        def _apply():
            self.format_combo['values'] = values
            if select_first and values:
                self.format_combo.current(0)
            else:
                self.format_combo.set(self.format_placeholder)
        self.run_on_ui_thread(_apply)

    def fetch_formats(self):
        self.detect_dependencies()
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Input Required", "Please enter a YouTube URL.")
            return
        if not self.ensure_js_runtime():
            return

        def _fetch():
            self.fetch_btn.config(state="disabled")
            self.download_btn.config(state="disabled")
            self.set_status("Fetching formats...")
            self.reset_progress()
            self.formats.clear()
            self.update_format_combo((), select_first=False)
            self.set_format_placeholder("Loading formats...")

            ydl_opts = self.build_ydl_opts()
            ydl_opts['skip_download'] = True
            ydl_opts['format'] = 'best'

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                    for format_info, requires_merge in self.get_format_candidates(info):
                        label = self.build_format_label(format_info, requires_merge)
                        self.formats.append((label, format_info['format_id'], requires_merge))

                    if not self.formats:
                        self.set_status("No compatible formats found for the current setup.")
                        self.update_format_combo((), select_first=False)
                        self.set_format_placeholder("No formats available")
                        return

                    self.update_format_combo([f[0] for f in self.formats], select_first=True)
                    if self.ffmpeg_location:
                        self.set_status("Formats loaded.")
                    else:
                        self.set_status("Formats loaded. Video-only entries will need FFmpeg; single-file entries will download directly.")
            except Exception as e:
                self.set_status("Failed to fetch formats.")
                self.reset_progress()
                self.update_format_combo((), select_first=False)
                self.set_format_placeholder("Fetch formats to try again")
                messagebox.showerror("Error", str(e))
            finally:
                self.fetch_btn.config(state="normal")
                self.download_btn.config(state="normal")

        threading.Thread(target=_fetch, daemon=True).start()

    def download_video(self):
        self.detect_dependencies()
        url = self.url_entry.get().strip()
        if not url or not self.formats:
            messagebox.showwarning("Missing Info", "Enter URL and select a format.")
            return
        if not self.ensure_js_runtime():
            return

        if self.format_combo.current() == -1:
            messagebox.showwarning("No Format Selected", "Please select a format to download.")
            return

        selected_format = self.formats[self.format_combo.current()]
        selected_format_id = selected_format[1]
        selected_format_requires_merge = selected_format[2]
        if selected_format_requires_merge and not self.ensure_ffmpeg():
            return

        def _download():
            self.fetch_btn.config(state="disabled")
            self.download_btn.config(state="disabled")
            self.set_status("Starting download...")
            self.reset_progress("ETA: Preparing...")

            def progress_hook(d):
                if d['status'] == 'downloading':
                    percent = self.clean_text(d.get('_percent_str', '').strip())
                    speed = self.clean_text(d.get('_speed_str', ''))
                    eta = self.clean_text(d.get('_eta_str', ''))
                    self.set_status("Downloading...")
                    self.update_progress(percent, eta, speed)
                elif d['status'] == 'finished':
                    if selected_format_requires_merge:
                        self.set_status("Download finished. Merging...")
                        self.update_progress("100", "Finalizing", "")
                    else:
                        self.set_status("Download finished.")
                        self.update_progress("100", "Done", "")

            ydl_opts = self.build_ydl_opts()
            ydl_opts.update({
                'format': f"{selected_format_id}+bestaudio" if selected_format_requires_merge else selected_format_id,
                'outtmpl': os.path.join(self.output_folder, '%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
            })

            if selected_format_requires_merge:
                ydl_opts.update({
                    'merge_output_format': 'mp4',
                    'postprocessors': [{
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': 'mp4',
                    }],
                })

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                self.set_status("Download complete.")
                self.update_progress("100", "Done", "")
                messagebox.showinfo("Success", "Video downloaded successfully!")
            except Exception as e:
                self.set_status("Download failed.")
                self.reset_progress()
                messagebox.showerror("Error", str(e))
            finally:
                self.fetch_btn.config(state="normal")
                self.download_btn.config(state="normal")

        threading.Thread(target=_download, daemon=True).start()


# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()
