import os
import sys
import threading
import time
import queue
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import yt_dlp
from yt_dlp.utils import DownloadCancelled, DownloadError, ExtractorError

# Priority 3 Modular Packages
import config
from config import (
    APP_NAME,
    APP_VERSION,
    APP_TITLE,
    DARK_COLORS,
    FONTS,
    DEFAULT_WINDOW_WIDTH,
    DEFAULT_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    MAX_NETWORK_RETRIES,
    INITIAL_RETRY_DELAY,
    BACKOFF_MULTIPLIER,
    HTTP_429_MAX_RETRIES,
    AUTH_BROWSER_DISPLAY_NAMES,
    AUTH_BROWSER_MAP,
    DEFAULT_AUTH_BROWSER_DISPLAY,
    MSG_RATE_LIMITED,
    MSG_BOT_CHALLENGE,
    MSG_AUTH_REQUIRED,
    MSG_COOKIE_ACCESS_FAILED,
    MSG_EXTRACTION_FAILED,
    get_cookie_access_error_message,
    get_base_dir,
    get_default_download_dir,
    ICON_ICO_PATH,
    ICON_PNG_PATH,
)
from utils.logging_config import logger
from utils.file_utils import (
    sanitize_filename as util_sanitize_filename,
    get_unique_filename as util_get_unique_filename,
    open_folder as util_open_folder,
    check_folder_writable,
)
from core.progress_tracker import DownloadProgressTracker
from core.ffmpeg_manager import (
    find_executable as core_find_executable,
    validate_ffmpeg_executable as core_validate_ffmpeg,
    find_ffmpeg as core_find_ffmpeg,
    detect_dependencies as core_detect_dependencies,
)
from core.format_manager import (
    safe_int,
    safe_float,
    format_filesize as core_format_filesize,
    is_valid_format as core_is_valid_format,
    is_valid_audio_format as core_is_valid_audio_format,
    format_sort_key as core_format_sort_key,
    format_resolution_label as core_format_res_label,
    get_format_candidates as core_get_format_candidates,
    get_audio_candidates as core_get_audio_candidates,
    build_format_label as core_build_format_label,
)
from core.metadata_manager import (
    format_duration as core_format_duration,
    format_view_count as core_format_view_count,
    download_and_process_thumbnail,
)
from core.downloader import (
    build_ydl_opts as core_build_ydl_opts,
    YTDLPLoggerAdapter,
    ErrorCategory,
    classify_error,
    is_permanent_error,
    is_transient_network_error,
    is_rate_limit_error,
    is_auth_required_error,
    is_restricted_content_error,
    is_bot_challenge_error,
    is_cookie_access_error,
    parse_retry_after,
    calculate_backoff_delay,
    sanitize_error_message,
    cleanup_temp_files as core_cleanup_temp_files,
)
from ui.main_window import configure_styles as ui_configure_styles, create_ui_widgets
from ui.dialogs import show_error, show_warning, show_info, get_ffmpeg_guidance_text


class YouTubeDownloaderApp:
    """YouTubeMate desktop downloader application controller and facade."""

    preview_card = None
    current_video_info = None
    current_video_title = None
    current_thumbnail_url = None
    _thumb_img = None
    video_formats = []
    audio_formats = []
    format_placeholder = "Fetch formats to choose a quality"

    is_fetching = False
    is_downloading = False
    is_closing = False
    active_worker = None
    _poll_timer_id = None
    _ui_poll_interval_ms = 20
    _DEFAULT_BROWSER = object()

    @property
    def _ui_queue(self):
        """Per-instance thread-safe UI callback queue. Lazily initialized if needed."""
        q = self.__dict__.get('_ui_queue_inst')
        if q is None:
            q = queue.Queue()
            self.__dict__['_ui_queue_inst'] = q
        return q

    @_ui_queue.setter
    def _ui_queue(self, val):
        self.__dict__['_ui_queue_inst'] = val

    @property
    def _state_lock(self):
        """Per-instance state lock. Lazily allocated if instantiated via __new__."""
        lock = self.__dict__.get('_state_lock_inst')
        if lock is None:
            lock = threading.Lock()
            self.__dict__['_state_lock_inst'] = lock
        return lock

    @_state_lock.setter
    def _state_lock(self, val):
        self.__dict__['_state_lock_inst'] = val

    @property
    def cancel_requested(self):
        """Per-instance cancellation event. Lazily allocated if instantiated via __new__."""
        event = self.__dict__.get('_cancel_requested_inst')
        if event is None:
            event = threading.Event()
            self.__dict__['_cancel_requested_inst'] = event
        return event

    @cancel_requested.setter
    def cancel_requested(self, val):
        self.__dict__['_cancel_requested_inst'] = val

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}")
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.root.resizable(True, True)
        self.apply_app_icon()

        self.app_dir = get_base_dir()
        self.output_folder = get_default_download_dir()

        self.formats = []
        self.video_formats = []
        self.audio_formats = []
        self.current_video_info = None
        self.current_video_title = None
        self.current_thumbnail_url = None
        self._thumb_img = None

        self.node_path = None
        self.js_runtime_name = None
        self.js_runtime_path = None
        self.ffmpeg_path = None
        self.ffmpeg_location = None
        self.ffmpeg_version = None

        # Lifecycle & Threading State
        self.is_fetching = False
        self.is_downloading = False
        self.is_closing = False
        self._state_lock = threading.Lock()
        self.active_worker = None
        self.cancel_requested = threading.Event()

        self.progress_value = tk.DoubleVar(master=self.root, value=0.0)
        self.eta_value = tk.StringVar(master=self.root, value="ETA: --")
        self.progress_text = tk.StringVar(master=self.root, value="0%")
        self.speed_value = tk.StringVar(master=self.root, value="Speed: --")
        self.warning_value = tk.StringVar(master=self.root, value="")
        self.download_mode_value = tk.StringVar(master=self.root, value="Video (MP4 / WebM)")
        self.auth_browser_value = tk.StringVar(master=self.root, value=DEFAULT_AUTH_BROWSER_DISPLAY)
        self.format_placeholder = "Fetch formats to choose a quality"

        self.detect_dependencies()
        self.configure_styles()
        self.create_widgets()
        self.center_window()
        self._start_ui_polling()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        logger.info("Application initialized. Root directory: %s", self.app_dir)

    def configure_styles(self):
        ui_configure_styles(self)

    def create_widgets(self):
        create_ui_widgets(self)

    def center_window(self):
        try:
            self.root.update_idletasks()
            w = int(self.root.winfo_width()) if str(self.root.winfo_width()).isdigit() else DEFAULT_WINDOW_WIDTH
            h = int(self.root.winfo_height()) if str(self.root.winfo_height()).isdigit() else DEFAULT_WINDOW_HEIGHT
            screen_w = int(self.root.winfo_screenwidth()) if str(self.root.winfo_screenwidth()).isdigit() else 1920
            screen_h = int(self.root.winfo_screenheight()) if str(self.root.winfo_screenheight()).isdigit() else 1080
            x = max(0, (screen_w // 2) - (w // 2))
            y = max(0, (screen_h // 2) - (h // 2))
            self.root.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def apply_app_icon(self):
        """Applies the custom YouTubeMate branding icon to window titlebar and taskbar."""
        if sys.platform == "win32":
            try:
                import ctypes
                myappid = f"YouTubeMate.Desktop.{APP_VERSION}"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        if hasattr(self, 'root') and self.root:
            if os.path.isfile(ICON_ICO_PATH):
                try:
                    self.root.iconbitmap(default=ICON_ICO_PATH)
                except Exception:
                    try:
                        self.root.iconbitmap(ICON_ICO_PATH)
                    except Exception:
                        pass
            if os.path.isfile(ICON_PNG_PATH):
                try:
                    from PIL import Image, ImageTk
                    with Image.open(ICON_PNG_PATH) as _icon_img:
                        self._app_icon_photo = ImageTk.PhotoImage(_icon_img.copy())
                    self.root.iconphoto(True, self._app_icon_photo)
                except Exception:
                    pass

    @staticmethod
    def clean_text(text):
        if text is None:
            return ""
        return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', str(text)).strip()

    def clean_status_value(self, label, value, fallback):
        val = self.clean_text(value)
        if not val or val in {"N/A", "NA", "Unknown"}:
            return f"{label}: {fallback}"
        return f"{label}: {val}"

    def parse_percent(self, percent_text):
        if not percent_text:
            return 0.0
        match = re.search(r'(-?\d+(?:\.\d+)?)', str(percent_text))
        return float(match.group(1)) if match else 0.0

    # --- Dependency Management ---

    def find_executable(self, executable_name):
        return core_find_executable(executable_name, app_dir=getattr(self, 'app_dir', None))

    def validate_ffmpeg_executable(self, ffmpeg_path):
        return core_validate_ffmpeg(ffmpeg_path)

    def validate_ffmpeg(self, ffmpeg_path):
        version = self.validate_ffmpeg_executable(ffmpeg_path)
        return (bool(version), version)

    def find_ffmpeg(self):
        return core_find_ffmpeg(app_dir=getattr(self, 'app_dir', None))

    def detect_dependencies(self):
        deps = core_detect_dependencies(app_dir=getattr(self, 'app_dir', None))
        self.node_path = deps["node_path"]
        self.js_runtime_name = deps["js_runtime_name"]
        self.js_runtime_path = deps["js_runtime_path"]
        self.ffmpeg_path = deps["ffmpeg_path"]
        self.ffmpeg_location = deps["ffmpeg_location"]
        self.ffmpeg_version = deps["ffmpeg_version"]

    def get_selected_browser(self):
        """Returns normalized browser identifier ('chrome', 'edge', 'firefox') or None."""
        if not hasattr(self, 'auth_browser_value') or not self.auth_browser_value:
            return None
        try:
            val = self.auth_browser_value.get() if hasattr(self.auth_browser_value, 'get') else str(self.auth_browser_value)
            self._cached_auth_browser = val
        except RuntimeError:
            val = getattr(self, '_cached_auth_browser', None) or config.DEFAULT_AUTH_BROWSER_DISPLAY
        return AUTH_BROWSER_MAP.get(val, None)

    def build_ydl_opts(self, logger_adapter=None, browser_name=_DEFAULT_BROWSER):
        b_name = self.get_selected_browser() if browser_name is self._DEFAULT_BROWSER else browser_name
        return core_build_ydl_opts(
            js_runtime_name=getattr(self, 'js_runtime_name', None),
            js_runtime_path=getattr(self, 'js_runtime_path', None),
            ffmpeg_location=getattr(self, 'ffmpeg_location', None),
            warning_callback=self.handle_ydlp_warning,
            browser_name=b_name,
            logger_adapter=logger_adapter,
        )

    class YTDLPLogger:
        def __init__(self, app):
            self.app = app

        def debug(self, msg):
            return

        def warning(self, msg):
            self.app.handle_ydlp_warning(msg)

        def error(self, msg):
            self.app.handle_ydlp_warning(msg)

    # --- Format Processing ---

    @staticmethod
    def _safe_int(value, default=0):
        return safe_int(value, default)

    @staticmethod
    def _safe_float(value, default=0.0):
        return safe_float(value, default)

    @staticmethod
    def format_filesize(value):
        return core_format_filesize(value)

    @staticmethod
    def _is_valid_format(f):
        return core_is_valid_format(f)

    @staticmethod
    def _is_valid_audio_format(f):
        return core_is_valid_audio_format(f)

    def _format_sort_key(self, f):
        return core_format_sort_key(f)

    @staticmethod
    def _format_resolution_label(height):
        return core_format_res_label(height)

    def get_format_candidates(self, info):
        return core_get_format_candidates(info)

    def get_audio_candidates(self, info):
        return core_get_audio_candidates(info, ffmpeg_location=getattr(self, 'ffmpeg_location', None))

    def build_format_label(self, format_info, requires_merge):
        return core_build_format_label(format_info, requires_merge, ffmpeg_location=getattr(self, 'ffmpeg_location', None))

    @staticmethod
    def format_duration(seconds):
        return core_format_duration(seconds)

    @staticmethod
    def format_view_count(views):
        return core_format_view_count(views)

    # --- Guards & Guidance ---

    def ensure_ffmpeg(self):
        if getattr(self, 'ffmpeg_path', None) and getattr(self, 'ffmpeg_location', None):
            return True
        self.set_status("FFmpeg is required for high-resolution formats.")
        self.show_ffmpeg_guidance(is_audio=False)
        return False

    def ensure_ffmpeg_for_audio(self, codec='mp3'):
        if getattr(self, 'ffmpeg_path', None) and getattr(self, 'ffmpeg_location', None):
            return True
        self.set_status(f"FFmpeg is required to convert audio to {codec.upper()}.")
        self.show_ffmpeg_guidance(is_audio=True, codec=codec)
        return False

    def ensure_js_runtime(self):
        if getattr(self, 'js_runtime_name', None) and getattr(self, 'js_runtime_path', None):
            return True
        self.set_status("No supported JavaScript runtime found. Install Node.js or Deno to continue.")
        self.show_error_message(
            "Runtime Required",
            "YouTube format extraction now requires a local JavaScript runtime to solve "
            "YouTube player challenges.\n\n"
            "Please install Node.js (https://nodejs.org) or Deno (https://deno.com), "
            "or place node.exe in a 'tools' folder next to YouTubeMate."
        )
        return False

    def get_startup_status(self):
        js_path = getattr(self, 'js_runtime_path', None)
        ff_loc = getattr(self, 'ffmpeg_location', None)
        ff_ver = getattr(self, 'ffmpeg_version', None)

        if js_path and ff_loc:
            ver_text = f" (v{ff_ver})" if ff_ver else ""
            return f"Ready. FFmpeg detected{ver_text}."
        if js_path and not ff_loc:
            return "Runtime detected. Some HD formats require FFmpeg."
        if not js_path and ff_loc:
            return "FFmpeg detected. Install Node.js for reliable extraction."
        return "Install Node.js & FFmpeg to enable all features."

    def show_error_message(self, title, message):
        self.run_on_ui_thread(show_error, title, message)

    def show_warning_message(self, title, message):
        self.run_on_ui_thread(show_warning, title, message)

    def show_info_message(self, title, message):
        self.run_on_ui_thread(show_info, title, message)

    def show_ffmpeg_guidance(self, is_audio=False, codec='mp3'):
        title, msg = get_ffmpeg_guidance_text(is_audio=is_audio, codec=codec)
        self.show_error_message("FFmpeg Required", msg)

    def open_output_folder(self):
        folder = getattr(self, 'output_folder', None)
        if not folder or not os.path.exists(folder):
            self.show_warning_message("Folder Missing", "Selected output folder does not exist.")
            return
        success = util_open_folder(folder)
        if not success:
            self.show_warning_message("Error", f"Could not open directory:\n{folder}")

    def get_download_mode(self):
        """Returns current download mode string safely across threads."""
        if not hasattr(self, 'download_mode_value') or not self.download_mode_value:
            return "Video (MP4 / WebM)"
        try:
            val = self.download_mode_value.get() if hasattr(self.download_mode_value, 'get') else str(self.download_mode_value)
            self._cached_download_mode = val
        except RuntimeError:
            val = getattr(self, '_cached_download_mode', None) or "Video (MP4 / WebM)"
        return val

    def on_download_mode_changed(self, event=None):
        mode = self.get_download_mode()
        if not hasattr(self, 'current_video_info') or not self.current_video_info:
            return

        if "Audio" in mode:
            if "MP3" in mode:
                self.formats = [f for f in self.audio_formats if len(f) > 5 and f[5] == 'mp3'] or self.audio_formats
            elif "M4A" in mode:
                self.formats = [f for f in self.audio_formats if len(f) > 5 and f[5] == 'm4a'] or self.audio_formats
            else:
                self.formats = self.audio_formats
        else:
            self.formats = self.video_formats

        if self.formats:
            values = [f[0] for f in self.formats]
            self.update_format_combo(values, select_first=True)
            self.set_status(f"Switched mode to {mode}. {len(self.formats)} format(s) available.")
        else:
            self.update_format_combo((), select_first=False)
            self.set_status(f"No formats available for {mode}.")

    # --- UI State & Preview ---

    def clear_metadata_preview(self):
        def _clear():
            if hasattr(self, 'meta_title_label') and self.meta_title_label:
                self.meta_title_label.config(text="Fetching video metadata...")
            if hasattr(self, 'meta_channel_label') and self.meta_channel_label:
                self.meta_channel_label.config(text="--")
            if hasattr(self, 'meta_duration_label') and self.meta_duration_label:
                self.meta_duration_label.config(text="--:--")
            if hasattr(self, 'meta_views_label') and self.meta_views_label:
                self.meta_views_label.config(text="--")
            if hasattr(self, 'thumb_label') and self.thumb_label:
                self.thumb_label.config(image="", text="Loading...")
            self._thumb_img = None
        self.run_on_ui_thread(_clear)

    def display_metadata_preview(self, info):
        if not info or not isinstance(info, dict):
            return

        title = info.get('title') or "Unknown Title"
        uploader = info.get('uploader') or info.get('channel') or "--"
        duration_str = self.format_duration(info.get('duration')) or "--:--"
        views_str = self.format_view_count(info.get('view_count')) or "--"
        thumb_url = info.get('thumbnail')

        def _update():
            if hasattr(self, 'meta_title_label') and self.meta_title_label:
                display_title = title if len(title) <= 90 else title[:87] + "..."
                self.meta_title_label.config(text=display_title)
            if hasattr(self, 'meta_channel_label') and self.meta_channel_label:
                self.meta_channel_label.config(text=uploader)
            if hasattr(self, 'meta_duration_label') and self.meta_duration_label:
                self.meta_duration_label.config(text=duration_str)
            if hasattr(self, 'meta_views_label') and self.meta_views_label:
                self.meta_views_label.config(text=views_str)

        self.run_on_ui_thread(_update)
        if thumb_url:
            self._load_thumbnail_async(thumb_url)

    def _load_thumbnail_async(self, thumb_url):
        def _worker():
            pil_img, out_path = download_and_process_thumbnail(thumb_url)

            def _show():
                img = None
                try:
                    if pil_img is not None:
                        from PIL import ImageTk
                        img = ImageTk.PhotoImage(pil_img)
                    elif out_path and os.path.exists(out_path):
                        img = tk.PhotoImage(file=out_path)
                        try:
                            os.remove(out_path)
                        except Exception:
                            pass
                    if img:
                        self._thumb_img = img
                        if hasattr(self, 'thumb_label') and self.thumb_label:
                            self.thumb_label.config(image=img, text="")
                except Exception as e:
                    logger.debug("Failed displaying thumbnail on UI thread: %s", e)

            self.run_on_ui_thread(_show)

        threading.Thread(target=_worker, daemon=True, name="ThumbnailWorker").start()

    def set_status(self, text):
        clean = self.clean_text(text)
        status_style = "Status.TLabel"
        lower_text = clean.lower()

        if any(keyword in lower_text for keyword in ("failed", "error", "no compatible formats", "cancelled")):
            status_style = "StatusError.TLabel"
        elif any(keyword in lower_text for keyword in ("loaded", "finished", "complete", "ready", "success")):
            status_style = "StatusSuccess.TLabel"
        elif any(keyword in lower_text for keyword in ("retrying", "warning")):
            status_style = "StatusWarning.TLabel"

        if hasattr(self, 'status_label') and self.status_label:
            self.run_on_ui_thread(self.status_label.config, text=clean, style=status_style)

    def update_progress(self, percent_text="", eta_text="", speed_text="", stage_text=None):
        clean_percent = self.clean_text(percent_text)
        clean_eta = self.clean_text(eta_text)
        clean_speed = self.clean_text(speed_text)
        percent_value = max(0.0, min(100.0, self.parse_percent(clean_percent)))
        eta_display = self.clean_status_value("ETA", clean_eta.replace("ETA:", "").strip(), "--")
        speed_display = self.clean_status_value("Speed", clean_speed.replace("Speed:", "").strip(), "--")

        if hasattr(self, 'progress_value') and self.progress_value:
            self.run_on_ui_thread(self.progress_value.set, percent_value)
        if hasattr(self, 'eta_value') and self.eta_value:
            self.run_on_ui_thread(self.eta_value.set, eta_display)
        if hasattr(self, 'speed_value') and self.speed_value:
            self.run_on_ui_thread(self.speed_value.set, speed_display)
        if hasattr(self, 'progress_text') and self.progress_text:
            self.run_on_ui_thread(self.progress_text.set, f"{int(round(percent_value))}%")
        if stage_text:
            self.set_status(stage_text)

    def reset_progress(self, eta_text="ETA: --"):
        if hasattr(self, 'progress_value') and self.progress_value:
            self.run_on_ui_thread(self.progress_value.set, 0.0)
        if hasattr(self, 'eta_value') and self.eta_value:
            clean_eta = self.clean_status_value("ETA", eta_text.replace("ETA:", "").strip(), "--")
            self.run_on_ui_thread(self.eta_value.set, clean_eta)
        if hasattr(self, 'speed_value') and self.speed_value:
            self.run_on_ui_thread(self.speed_value.set, "Speed: --")
        if hasattr(self, 'progress_text') and self.progress_text:
            self.run_on_ui_thread(self.progress_text.set, "0%")
        if hasattr(self, 'warning_value') and self.warning_value:
            self.run_on_ui_thread(self.warning_value.set, "")

    def handle_ydlp_warning(self, message):
        msg = self.clean_text(message)
        logger.warning("[yt-dlp] %s", msg)
        lower_msg = msg.lower()
        if "n challenge solving failed" in lower_msg or "error solving n challenge request" in lower_msg:
            msg = "YouTube returned a slow challenge response. Some formats may be missing for this fetch. Try again if needed."
        elif is_cookie_access_error(msg):
            msg = get_cookie_access_error_message(self.get_selected_browser() or msg)
        elif msg.startswith("WARNING:"):
            msg = msg.replace("WARNING:", "", 1).strip()
        elif msg.startswith("ERROR:"):
            msg = re.sub(r'^(?:ERROR:\s*)+', '', msg).strip()
        if hasattr(self, 'warning_value') and self.warning_value:
            self.run_on_ui_thread(self.warning_value.set, msg[:220])

    def set_controls_state(self, enabled):
        state = "normal" if enabled else "disabled"
        if hasattr(self, 'fetch_btn') and self.fetch_btn:
            self.fetch_btn.config(state=state)
        if hasattr(self, 'download_btn') and self.download_btn:
            self.download_btn.config(state=state)

    def set_ui_state(self, state):
        def _apply():
            if state in ("fetching", "downloading"):
                if hasattr(self, 'fetch_btn') and self.fetch_btn:
                    self.fetch_btn.config(state="disabled")
                if hasattr(self, 'download_btn') and self.download_btn:
                    self.download_btn.config(state="disabled")
                if hasattr(self, 'cancel_btn') and self.cancel_btn:
                    self.cancel_btn.config(state="normal")
                if hasattr(self, 'mode_combo') and self.mode_combo:
                    self.mode_combo.config(state="disabled")
                if hasattr(self, 'auth_browser_combo') and self.auth_browser_combo:
                    self.auth_browser_combo.config(state="disabled")
            elif state == "shutting_down":
                if hasattr(self, 'fetch_btn') and self.fetch_btn:
                    self.fetch_btn.config(state="disabled")
                if hasattr(self, 'download_btn') and self.download_btn:
                    self.download_btn.config(state="disabled")
                if hasattr(self, 'cancel_btn') and self.cancel_btn:
                    self.cancel_btn.config(state="disabled")
                if hasattr(self, 'auth_browser_combo') and self.auth_browser_combo:
                    self.auth_browser_combo.config(state="disabled")
            else:  # idle / completed
                if hasattr(self, 'fetch_btn') and self.fetch_btn:
                    self.fetch_btn.config(state="normal")
                if hasattr(self, 'cancel_btn') and self.cancel_btn:
                    self.cancel_btn.config(state="disabled")
                if hasattr(self, 'mode_combo') and self.mode_combo:
                    self.mode_combo.config(state="readonly")
                if hasattr(self, 'auth_browser_combo') and self.auth_browser_combo:
                    self.auth_browser_combo.config(state="readonly")
                has_selection = False
                if hasattr(self, 'format_combo') and self.format_combo:
                    try:
                        curr = self.format_combo.current() if callable(self.format_combo.current) else self.format_combo.current
                        has_selection = (curr != -1)
                    except Exception:
                        has_selection = False
                if hasattr(self, 'download_btn') and self.download_btn:
                    self.download_btn.config(state="normal" if has_selection else "disabled")
        self.run_on_ui_thread(_apply)

    def cancel_active_download(self):
        with self._state_lock:
            if not self.is_downloading and not self.is_fetching:
                logger.info("Cancel requested but no active operation was in progress.")
                return
            logger.info("User requested cancellation.")
            self.cancel_requested.set()
        self.set_status("Cancelling download...")
        if hasattr(self, 'cancel_btn') and self.cancel_btn:
            self.cancel_btn.config(state="disabled")

    def cancel_download(self):
        """Backwards-compatible alias for cancel_active_download."""
        self.cancel_active_download()

    def _start_ui_polling(self):
        """Starts recurring UI queue polling loop on the main thread."""
        if getattr(self, '_poll_timer_id', None) is not None or getattr(self, 'is_closing', False):
            return
        if hasattr(self, 'root') and self.root:
            try:
                winfo = getattr(self.root, 'winfo_exists', None)
                if winfo is None or winfo():
                    self._poll_timer_id = self.root.after(self._ui_poll_interval_ms, self._poll_ui_queue)
            except (tk.TclError, RuntimeError):
                self._poll_timer_id = None

    def _stop_ui_polling(self):
        """Cancels recurring UI queue polling timer."""
        timer_id = getattr(self, '_poll_timer_id', None)
        if timer_id is not None:
            if hasattr(self, 'root') and self.root:
                try:
                    winfo = getattr(self.root, 'winfo_exists', None)
                    if winfo is None or winfo():
                        self.root.after_cancel(timer_id)
                except (tk.TclError, RuntimeError):
                    pass
            self._poll_timer_id = None

    def _poll_ui_queue(self):
        """Processes queued UI callbacks on the main thread and reschedules next poll."""
        self._poll_timer_id = None
        if getattr(self, 'is_closing', False):
            return

        processed = 0
        max_per_tick = 50
        while processed < max_per_tick:
            try:
                cb, args, kwargs = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            processed += 1
            try:
                if not getattr(self, 'is_closing', False):
                    cb(*args, **kwargs)
            except (tk.TclError, RuntimeError) as e:
                logger.debug("Suppressed Tkinter error during callback on UI thread: %s", e)
            except Exception as e:
                logger.error("Unhandled exception in UI callback: %s", e, exc_info=True)

        if not getattr(self, 'is_closing', False):
            if hasattr(self, 'root') and self.root:
                try:
                    winfo = getattr(self.root, 'winfo_exists', None)
                    if winfo is None or winfo():
                        self._poll_timer_id = self.root.after(self._ui_poll_interval_ms, self._poll_ui_queue)
                except (tk.TclError, RuntimeError):
                    self._poll_timer_id = None

    def drain_ui_queue(self):
        """Helper to synchronously drain all pending UI callbacks (useful in tests)."""
        while not self._ui_queue.empty():
            try:
                cb, args, kwargs = self._ui_queue.get_nowait()
                if not getattr(self, 'is_closing', False):
                    cb(*args, **kwargs)
            except queue.Empty:
                break
            except (tk.TclError, RuntimeError) as e:
                logger.debug("Suppressed Tkinter error during callback on UI thread: %s", e)
            except Exception as e:
                logger.error("Unhandled exception in drained UI callback: %s", e, exc_info=True)

    def run_on_ui_thread(self, callback, *args, **kwargs):
        """Dispatches callback to the Tkinter UI thread.

        If already on the main thread, executes synchronously (fast-path).
        If called from a worker thread, enqueues the callback into _ui_queue without
        calling any Tkinter APIs (preventing Python 3.14 threading RuntimeErrors).
        """
        if getattr(self, 'is_closing', False):
            return

        if threading.current_thread() is threading.main_thread():
            if not getattr(self, 'is_closing', False):
                try:
                    if hasattr(self, 'root') and self.root:
                        winfo = getattr(self.root, 'winfo_exists', None)
                        if winfo and not winfo():
                            return
                    callback(*args, **kwargs)
                except (tk.TclError, RuntimeError) as e:
                    logger.debug("Suppressed Tkinter error during direct callback on UI thread: %s", e)
                except Exception as e:
                    logger.error("Unhandled exception in direct UI callback: %s", e, exc_info=True)
        else:
            self._ui_queue.put((callback, args, kwargs))

    def select_output_folder(self):
        folder = filedialog.askdirectory(initialdir=getattr(self, 'output_folder', None))
        if folder:
            self.output_folder = folder
            if hasattr(self, 'folder_label') and self.folder_label:
                self.folder_label.config(text=folder)
            logger.info("Output folder updated: %s", folder)

    def set_format_placeholder(self, text=None):
        placeholder = text or getattr(self, 'format_placeholder', "Select quality")
        if hasattr(self, 'format_combo') and self.format_combo:
            self.run_on_ui_thread(self.format_combo.set, placeholder)

    def update_format_combo(self, values, select_first=False):
        def _apply():
            try:
                self.format_combo['values'] = values
                if select_first and values:
                    self.format_combo.current(0)
                    if hasattr(self, 'download_btn') and self.download_btn:
                        self.download_btn.config(state="normal")
                else:
                    self.format_combo.set(getattr(self, 'format_placeholder', "Fetch formats to choose a quality"))
                    if hasattr(self, 'download_btn') and self.download_btn:
                        self.download_btn.config(state="disabled")
            except (tk.TclError, RuntimeError):
                pass
        self.run_on_ui_thread(_apply)

    # --- File Management Helpers ---

    @staticmethod
    def sanitize_filename(name):
        return util_sanitize_filename(name)

    @staticmethod
    def get_unique_filename(folder, base_name, ext):
        return util_get_unique_filename(folder, base_name, ext)

    def _cleanup_temp_files(self, current_temp_files, max_retries=5, delay=0.1):
        core_cleanup_temp_files(current_temp_files, retries=max_retries, delay=delay)

    # --- Fetch Formats Workflow ---

    def fetch_formats(self):
        with self._state_lock:
            if self.is_fetching or self.is_downloading or self.is_closing:
                logger.warning("Fetch requested while another operation is in progress.")
                return
            self.is_fetching = True

        self.detect_dependencies()
        url = self.url_entry.get().strip()
        if not url:
            with self._state_lock:
                self.is_fetching = False
            self.show_warning_message("Input Required", "Please enter a YouTube URL.")
            self.set_ui_state("idle")
            return
        if not self.ensure_js_runtime():
            with self._state_lock:
                self.is_fetching = False
            self.set_ui_state("idle")
            return

        if hasattr(self, 'cancel_requested') and self.cancel_requested:
            self.cancel_requested.clear()
        self.set_ui_state("fetching")
        self.set_status("Fetching formats...")
        self.reset_progress()
        self.formats.clear()
        self.video_formats.clear()
        self.audio_formats.clear()
        self.clear_metadata_preview()
        self.update_format_combo((), select_first=False)
        self.set_format_placeholder("Loading formats...")

        selected_browser = self.get_selected_browser()
        current_mode = self.get_download_mode()

        def _fetch():
            ydl_opts = self.build_ydl_opts(browser_name=selected_browser)
            ydl_opts['skip_download'] = True

            info = None
            max_retries = 2
            try:
                for attempt in range(max_retries + 1):
                    logger_adapter = YTDLPLoggerAdapter(self.handle_ydlp_warning)
                    ydl_opts['logger'] = logger_adapter
                    try:
                        if self.cancel_requested.is_set():
                            logger.info("Fetch cancelled prior to execution.")
                            self.set_status("Fetch cancelled.")
                            return

                        logger.info("Extracting formats for URL: %s (attempt %d/%d)", url, attempt + 1, max_retries + 1)
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(url, download=False)
                        break
                    except Exception as e:
                        if self.cancel_requested.is_set():
                            self.set_status("Fetch cancelled.")
                            return

                        saw_429 = getattr(logger_adapter, 'saw_rate_limit', False)
                        category = classify_error(e, saw_rate_limit=saw_429)
                        sanitized = sanitize_error_message(str(e))

                        if category == ErrorCategory.COOKIE_DATABASE_ACCESS:
                            friendly_msg = get_cookie_access_error_message(selected_browser or sanitized)
                            logger.error("Browser cookie database access failed (%s) during format extraction: %s", category, sanitized)
                            self.set_status("Unable to access browser cookies.")
                            self.reset_progress()
                            self.update_format_combo((), select_first=False)
                            self.set_format_placeholder("Fetch formats to try again")
                            self.show_error_message("Cookie Access Error", friendly_msg)
                            return

                        if category == ErrorCategory.AUTH_REQUIRED:
                            if is_restricted_content_error(sanitized):
                                logger.warning("YouTube restricted content requires authentication: %s", sanitized)
                                self.set_status("Restricted content.")
                                self.reset_progress()
                                self.update_format_combo((), select_first=False)
                                self.set_format_placeholder("Restricted content")
                                self.show_error_message("Authentication Required", MSG_AUTH_REQUIRED)
                            else:
                                logger.warning("YouTube request limit or bot challenge on public video: %s", sanitized)
                                self.set_status("YouTube rate limit reached.")
                                self.reset_progress()
                                self.update_format_combo((), select_first=False)
                                self.set_format_placeholder("Fetch formats to try again")
                                self.show_error_message("Rate Limit Exceeded", MSG_RATE_LIMITED)
                            return

                        if category == ErrorCategory.RATE_LIMITED and attempt < max_retries:
                            retry_after = parse_retry_after(e)
                            if retry_after is None and getattr(logger_adapter, 'retry_after', None) is not None:
                                retry_after = logger_adapter.retry_after
                            delay = calculate_backoff_delay(attempt, retry_after=retry_after)
                            logger.warning("YouTube rate limit (HTTP 429). Retrying in %.1fs (attempt %d/%d)...", delay, attempt + 1, max_retries)
                            self.set_status(f"Rate limited by YouTube. Retrying in {delay:.0f}s...")
                            if self.cancel_requested.wait(timeout=delay):
                                self.set_status("Fetch cancelled.")
                                return
                            continue

                        if category == ErrorCategory.TRANSIENT_NETWORK and attempt < max_retries:
                            delay = INITIAL_RETRY_DELAY * (BACKOFF_MULTIPLIER ** attempt)
                            logger.warning("Transient network error: %s. Retrying in %.1fs (attempt %d/%d)...", sanitized, delay, attempt + 1, max_retries)
                            self.set_status(f"Network timeout. Retrying in {delay:.0f}s...")
                            if self.cancel_requested.wait(timeout=delay):
                                self.set_status("Fetch cancelled.")
                                return
                            continue

                        # Terminal error or retries exhausted
                        logger.error("Failed to fetch formats (%s): %s", category, sanitized, exc_info=True)
                        self.reset_progress()
                        self.update_format_combo((), select_first=False)
                        self.set_format_placeholder("Fetch formats to try again")

                        if category == ErrorCategory.RATE_LIMITED:
                            self.set_status("YouTube rate limit reached.")
                            self.show_error_message("Rate Limit Exceeded", MSG_RATE_LIMITED)
                        elif category == ErrorCategory.PERMANENT:
                            self.set_status("Video unavailable.")
                            self.show_error_message("Video Unavailable", sanitized)
                        else:
                            self.set_status("Failed to fetch formats.")
                            self.show_error_message("Extraction Error", MSG_EXTRACTION_FAILED)
                        return

                if self.cancel_requested.is_set():
                    logger.info("Fetch cancelled after extraction.")
                    self.set_status("Fetch cancelled.")
                    return

                self.current_video_info = info
                self.current_video_title = info.get('title') or "Video"
                self.current_thumbnail_url = info.get('thumbnail')
                self.display_metadata_preview(info)

                for format_info, requires_merge in self.get_format_candidates(info):
                    label = self.build_format_label(format_info, requires_merge)
                    self.video_formats.append((label, format_info['format_id'], requires_merge, format_info, False, None))

                self.audio_formats = self.get_audio_candidates(info)

                if "Audio" in current_mode:
                    if "MP3" in current_mode:
                        self.formats = [f for f in self.audio_formats if len(f) > 5 and f[5] == 'mp3'] or self.audio_formats
                    elif "M4A" in current_mode:
                        self.formats = [f for f in self.audio_formats if len(f) > 5 and f[5] == 'm4a'] or self.audio_formats
                    else:
                        self.formats = self.audio_formats
                else:
                    self.formats = self.video_formats

                if not self.formats and not self.video_formats and not self.audio_formats:
                    self.set_status("No compatible formats found.")
                    self.reset_progress()
                    self.update_format_combo((), select_first=False)
                    self.set_format_placeholder("No compatible formats found")
                    return

                labels = [f[0] for f in self.formats]
                self.update_format_combo(labels, select_first=True)
                self.set_status(f"Formats loaded. {len(self.formats)} format(s) available.")
                logger.info("Formats fetched successfully: %d video candidates, %d audio candidates.", len(self.video_formats), len(self.audio_formats))

            except Exception as e:
                logger.error("Error processing formats: %s", e, exc_info=True)
                self.set_status("Failed to parse formats.")
                self.show_error_message("Error", str(e))
            finally:
                with self._state_lock:
                    self.is_fetching = False
                    self.active_worker = None
                self.set_ui_state("idle")

        with self._state_lock:
            self.active_worker = threading.Thread(target=_fetch, daemon=True, name="FetchWorker")
            self.active_worker.start()

    # --- Download Workflow ---

    def download_video(self):
        with self._state_lock:
            if self.is_downloading or self.is_fetching or self.is_closing:
                logger.warning("Download requested while another operation is in progress.")
                return
            self.is_downloading = True

        url = self.url_entry.get().strip()
        if not url or not self.formats:
            with self._state_lock:
                self.is_downloading = False
            self.show_warning_message("Missing Info", "Enter URL and select a format.")
            self.set_ui_state("idle")
            return
        if not self.ensure_js_runtime():
            with self._state_lock:
                self.is_downloading = False
            self.set_ui_state("idle")
            return

        if self.format_combo.current() == -1:
            with self._state_lock:
                self.is_downloading = False
            self.show_warning_message("No Format Selected", "Please select a format to download.")
            self.set_ui_state("idle")
            return

        # Verify destination folder is writable
        folder = getattr(self, 'output_folder', None) or os.getcwd()
        is_writable, perm_err = check_folder_writable(folder)
        if not is_writable:
            with self._state_lock:
                self.is_downloading = False
            self.show_error_message("Destination Error", f"Cannot write to output folder:\n{perm_err}\n\nPlease select another directory.")
            self.set_ui_state("idle")
            return

        selected_format = self.formats[self.format_combo.current()]
        selected_format_id = selected_format[1]
        selected_format_requires_merge = selected_format[2]
        format_info = selected_format[3] if len(selected_format) > 3 else {}
        is_audio = selected_format[4] if len(selected_format) > 4 else False
        audio_codec = selected_format[5] if len(selected_format) > 5 else None
        video_size = format_info.get('filesize') or format_info.get('filesize_approx')

        if is_audio and audio_codec == 'mp3':
            if not self.ensure_ffmpeg_for_audio():
                with self._state_lock:
                    self.is_downloading = False
                self.set_ui_state("idle")
                return
        elif selected_format_requires_merge and not self.ensure_ffmpeg():
            with self._state_lock:
                self.is_downloading = False
            self.set_ui_state("idle")
            return

        if hasattr(self, 'cancel_requested') and self.cancel_requested:
            self.cancel_requested.clear()
        self.set_ui_state("downloading")
        self.set_status("Starting download...")
        self.reset_progress("ETA: Preparing...")

        selected_browser = self.get_selected_browser()

        if is_audio:
            if audio_codec == 'mp3':
                format_spec = 'bestaudio/best'
                target_ext = 'mp3'
            else:
                format_spec = selected_format_id if selected_format_id and selected_format_id != 'bestaudio/best' else 'bestaudio[ext=m4a]/bestaudio/best'
                target_ext = 'm4a'
        else:
            if selected_format_requires_merge:
                format_spec = f"{selected_format_id}+bestaudio[ext=m4a]/bestaudio"
                target_ext = 'mp4'
            else:
                format_spec = selected_format_id
                target_ext = format_info.get('ext') or 'mp4'

        video_title = getattr(self, 'current_video_title', None) or "video"
        unique_base = self.get_unique_filename(folder, video_title, target_ext)
        safe_base = unique_base.replace('%', '%%')
        outtmpl = os.path.join(folder, f"{safe_base}.%(ext)s")

        def _download():
            current_temp_files = set()

            def progress_hook(d):
                if self.cancel_requested.is_set():
                    raise yt_dlp.utils.DownloadCancelled("Download cancelled by user.")

                tmp = d.get('tmpfilename') or d.get('filename')
                if tmp and (tmp.endswith('.part') or tmp.endswith('.ytdl')):
                    current_temp_files.add(tmp)

                tracker.hook(d)

            def postprocessor_hook(d):
                if self.cancel_requested.is_set():
                    raise yt_dlp.utils.DownloadCancelled("Download cancelled by user.")
                if d.get('status') == 'started':
                    self.set_status("Processing audio/video streams...")
                    self.update_progress(96.0, "Processing...", "")

            def on_progress_update(percent, eta, speed, stage_text):
                self.set_status(stage_text)
                self.update_progress(percent, eta, speed)

            tracker = DownloadProgressTracker(
                requires_merge=selected_format_requires_merge,
                on_progress=on_progress_update,
                video_size=video_size,
            )

            ydl_opts = self.build_ydl_opts(browser_name=selected_browser)
            ydl_opts.update({
                'format': format_spec,
                'outtmpl': outtmpl,
                'progress_hooks': [progress_hook],
                'postprocessor_hooks': [postprocessor_hook],
            })

            if is_audio and audio_codec == 'mp3':
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            elif selected_format_requires_merge:
                ydl_opts['merge_output_format'] = 'mp4'

            # Resilient download loop with transient network retry
            max_retries = MAX_NETWORK_RETRIES
            for attempt in range(max_retries + 1):
                logger_adapter = YTDLPLoggerAdapter(self.handle_ydlp_warning)
                ydl_opts['logger'] = logger_adapter
                try:
                    logger.info("Download started (attempt %d/%d): format=%s, url=%s", attempt + 1, max_retries + 1, format_spec, url)
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])

                    if not self.cancel_requested.is_set():
                        logger.info("Download completed successfully.")
                        self.set_status("Download complete.")
                        self.update_progress(100.0, "Done", "")
                        self.show_info_message("Success", "Video downloaded successfully!")
                    break

                except yt_dlp.utils.DownloadCancelled:
                    logger.info("Download cancelled by user. Cleaning up partial files...")
                    self.set_status("Download cancelled.")
                    self.reset_progress("ETA: Cancelled")
                    self._cleanup_temp_files(current_temp_files)
                    break

                except Exception as e:
                    if self.cancel_requested.is_set():
                        logger.info("Download cancelled during execution. Cleaning up...")
                        self.set_status("Download cancelled.")
                        self.reset_progress("ETA: Cancelled")
                        self._cleanup_temp_files(current_temp_files)
                        break

                    saw_429 = getattr(logger_adapter, 'saw_rate_limit', False)
                    category = classify_error(e, saw_rate_limit=saw_429)
                    sanitized = sanitize_error_message(str(e))

                    if category == ErrorCategory.COOKIE_DATABASE_ACCESS:
                        friendly_msg = get_cookie_access_error_message(selected_browser or sanitized)
                        logger.error("Browser cookie database access failed (%s) during download: %s", category, sanitized)
                        self.set_status("Unable to access browser cookies.")
                        self.reset_progress()
                        self._cleanup_temp_files(current_temp_files)
                        self.show_error_message("Cookie Access Error", friendly_msg)
                        break

                    if category == ErrorCategory.AUTH_REQUIRED:
                        if is_restricted_content_error(sanitized):
                            logger.warning("YouTube restricted content requires authentication during download: %s", sanitized)
                            self.set_status("Restricted content.")
                            self.reset_progress()
                            self._cleanup_temp_files(current_temp_files)
                            self.show_error_message("Authentication Required", MSG_AUTH_REQUIRED)
                        else:
                            logger.warning("YouTube request limit or bot challenge during download: %s", sanitized)
                            self.set_status("YouTube rate limit reached.")
                            self.reset_progress()
                            self._cleanup_temp_files(current_temp_files)
                            self.show_error_message("Rate Limit Exceeded", MSG_RATE_LIMITED)
                        break

                    if category == ErrorCategory.RATE_LIMITED and attempt < max_retries and not self.cancel_requested.is_set():
                        retry_after = parse_retry_after(e)
                        if retry_after is None and getattr(logger_adapter, 'retry_after', None) is not None:
                            retry_after = logger_adapter.retry_after
                        delay = calculate_backoff_delay(attempt, retry_after=retry_after)
                        logger.warning("YouTube rate limit (HTTP 429) during download. Retrying in %.1fs (attempt %d/%d)...", delay, attempt + 1, max_retries)
                        self.set_status(f"Rate limited by YouTube. Retrying in {delay:.0f}s...")
                        if self.cancel_requested.wait(timeout=delay):
                            self.set_status("Download cancelled.")
                            self.reset_progress("ETA: Cancelled")
                            self._cleanup_temp_files(current_temp_files)
                            break
                        continue

                    if category == ErrorCategory.TRANSIENT_NETWORK and attempt < max_retries and not self.cancel_requested.is_set():
                        delay = INITIAL_RETRY_DELAY * (BACKOFF_MULTIPLIER ** attempt)
                        logger.warning("Transient network error: %s. Retrying in %.1fs (attempt %d/%d)...", sanitized, delay, attempt + 1, max_retries)
                        self.set_status(f"Network error. Retrying in {delay:.0f}s (attempt {attempt + 1}/{max_retries})...")
                        if self.cancel_requested.wait(timeout=delay):
                            self.set_status("Download cancelled.")
                            self.reset_progress("ETA: Cancelled")
                            self._cleanup_temp_files(current_temp_files)
                            break
                        continue

                    # Terminal / exhausted retries
                    logger.error("Download failed (%s): %s", category, sanitized, exc_info=True)
                    self.reset_progress()
                    self._cleanup_temp_files(current_temp_files)

                    if category == ErrorCategory.RATE_LIMITED:
                        self.set_status("YouTube rate limit reached.")
                        self.show_error_message("Rate Limit Exceeded", MSG_RATE_LIMITED)
                    elif category == ErrorCategory.PERMANENT:
                        self.set_status("Video unavailable.")
                        self.show_error_message("Video Unavailable", sanitized)
                    else:
                        self.set_status("Download failed.")
                        self.show_error_message("Download Error", MSG_EXTRACTION_FAILED)
                    break

            with self._state_lock:
                self.is_downloading = False
                self.active_worker = None
            self.set_ui_state("idle")

        with self._state_lock:
            self.active_worker = threading.Thread(target=_download, daemon=True, name="DownloadWorker")
            self.active_worker.start()

    # --- Application Shutdown ---

    def on_closing(self):
        if self.is_closing:
            return

        is_busy = False
        with self._state_lock:
            is_busy = (self.is_downloading or self.is_fetching) and self.active_worker and self.active_worker.is_alive()

        if is_busy:
            operation = "download" if self.is_downloading else "format fetch"
            if not messagebox.askyesno("Confirm Exit", f"A {operation} is currently in progress.\n\nDo you want to cancel it and exit?"):
                return

            self.is_closing = True
            logger.info("Window closing with active %s. Initiating non-blocking shutdown...", operation)
            self.cancel_requested.set()
            self._stop_ui_polling()
            self.set_ui_state("shutting_down")
            self.set_status(f"Cancelling {operation} and shutting down...")

            shutdown_deadline = time.time() + 4.0
            self._poll_worker_shutdown(shutdown_deadline)
        else:
            self.is_closing = True
            self._destroy_root()

    def _poll_worker_shutdown(self, deadline):
        worker = self.active_worker
        if worker and worker.is_alive() and time.time() < deadline:
            try:
                if self.root and self.root.winfo_exists():
                    self.root.after(50, lambda: self._poll_worker_shutdown(deadline))
            except (tk.TclError, RuntimeError):
                pass
        else:
            if worker and worker.is_alive():
                logger.warning("Worker thread did not terminate within shutdown timeout; proceeding with exit.")
            else:
                logger.info("Worker thread stopped cleanly.")
            self._destroy_root()

    def _destroy_root(self):
        self.is_closing = True
        self._stop_ui_polling()
        try:
            while not self._ui_queue.empty():
                self._ui_queue.get_nowait()
        except Exception:
            pass
        try:
            if hasattr(self, 'root') and self.root:
                self.root.destroy()
        except (tk.TclError, RuntimeError):
            pass


# Application Entry Point
if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"YouTubeMate.Desktop.{APP_VERSION}")
        except Exception:
            pass
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()
