import os
import sys

APP_NAME = "YouTubeMate"
APP_VERSION = "2.0.0"
APP_TITLE = f"{APP_NAME} — YouTube Video & Audio Downloader"

DEFAULT_WINDOW_WIDTH = 800
DEFAULT_WINDOW_HEIGHT = 680
MIN_WINDOW_WIDTH = 760
MIN_WINDOW_HEIGHT = 600

# Theme & Color Palettes
# Existing brand colors: primary #4A6FA5, success #4CAF50, error #E57373
DARK_COLORS = {
    "bg": "#121316",
    "card": "#1E1F24",
    "card_alt": "#25272F",
    "card_hover": "#2B2D37",
    "primary": "#4A6FA5",
    "primary_hover": "#3F618F",
    "text": "#F3F4F6",
    "secondary_text": "#9CA3AF",
    "border": "#2E3039",
    "success": "#4CAF50",
    "error": "#E57373",
    "warning": "#F59E0B",
    "button_surface": "#282A34",
    "button_hover": "#333644",
    "entry_bg": "#18191E",
    "entry_fg": "#F3F4F6",
    "progressbar_bg": "#282A34",
    "badge_bg": "#2D303E",
}

LIGHT_COLORS = {
    "bg": "#F7F9FB",
    "card": "#FFFFFF",
    "card_alt": "#F3F4F6",
    "card_hover": "#E5E7EB",
    "primary": "#4A6FA5",
    "primary_hover": "#3F618F",
    "text": "#2E2E2E",
    "secondary_text": "#6B7280",
    "border": "#E5E7EB",
    "success": "#4CAF50",
    "error": "#E57373",
    "warning": "#D97706",
    "button_surface": "#EEF2F6",
    "button_hover": "#E3E8EF",
    "entry_bg": "#FFFFFF",
    "entry_fg": "#2E2E2E",
    "progressbar_bg": "#E5E7EB",
    "badge_bg": "#E2E8F0",
}

# Typography
FONTS = {
    "title": ("Segoe UI", 18, "bold"),
    "subtitle": ("Segoe UI", 10),
    "section": ("Segoe UI Semibold", 10),
    "label": ("Segoe UI", 10),
    "input": ("Segoe UI", 10),
    "button": ("Segoe UI Semibold", 10),
    "status": ("Segoe UI", 10),
    "badge": ("Segoe UI", 9, "bold"),
    "small": ("Segoe UI", 9),
    "code": ("Consolas", 9),
}

# Network & Download Configuration
SOCKET_TIMEOUT = 30
EXTRACTOR_RETRIES = 5
MAX_NETWORK_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0
BACKOFF_MULTIPLIER = 2.0

# Rate-Limit & Backoff Configuration
HTTP_429_MAX_RETRIES = 2
HTTP_429_INITIAL_DELAY = 3.0
HTTP_429_BACKOFF_FACTOR = 2.0
HTTP_429_MAX_DELAY = 15.0
JITTER_RATIO = 0.25

# Browser Authentication Settings
SUPPORTED_AUTH_BROWSERS = [
    ("None (Unauthenticated)", None),
    ("Google Chrome", "chrome"),
    ("Microsoft Edge", "edge"),
    ("Firefox", "firefox"),
]
AUTH_BROWSER_DISPLAY_NAMES = [name for name, _ in SUPPORTED_AUTH_BROWSERS]
AUTH_BROWSER_MAP = {name: val for name, val in SUPPORTED_AUTH_BROWSERS}
DEFAULT_AUTH_BROWSER_DISPLAY = AUTH_BROWSER_DISPLAY_NAMES[0]

# User-Facing Error Messages (Sanitized)
MSG_RATE_LIMITED = "YouTube is temporarily limiting requests. Please wait before trying again."
MSG_BOT_CHALLENGE = "YouTube is temporarily limiting automated requests. Please wait before trying again."
MSG_AUTH_REQUIRED = (
    "This video requires authentication (for example, age-restricted, private, or members-only content). "
    "If you have access, you can optionally select your signed-in browser under Browser Auth."
)
MSG_COOKIE_ACCESS_FAILED = (
    "Unable to access Chrome cookies. Close all Chrome windows and background processes, "
    "then try again. Alternatively, select another browser where you are signed into YouTube."
)
MSG_EXTRACTION_FAILED = "Unable to retrieve video information. Check your connection and try again."


def get_cookie_access_error_message(browser_name=None):
    """Returns a user-friendly, actionable cookie access failure message for the selected browser."""
    b_lower = str(browser_name or "").strip().lower()
    if "edge" in b_lower:
        display_name = "Edge"
    elif "firefox" in b_lower:
        display_name = "Firefox"
    elif "chrome" in b_lower:
        display_name = "Chrome"
    elif browser_name and b_lower not in ("none", "none (unauthenticated)"):
        display_name = str(browser_name).strip()
    else:
        display_name = "browser"

    return (
        f"Unable to access {display_name} cookies. Close all {display_name} windows and background processes, "
        f"then try again. Alternatively, select another browser where you are signed into YouTube."
    )

STANDARD_RESOLUTIONS = [2160, 1440, 1080, 720, 480, 360, 240, 144]


def get_base_dir():
    """Returns application root directory, handling PyInstaller _MEIPASS bundle mode."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(relative_path):
    """Returns absolute path to a bundled or development resource."""
    base = get_base_dir()
    return os.path.join(base, relative_path)


ASSETS_DIR = get_resource_path("assets")
ICON_ICO_PATH = os.path.join(ASSETS_DIR, "icon.ico")
ICON_PNG_PATH = os.path.join(ASSETS_DIR, "icon.png")


def get_default_download_dir():
    """Returns user's default Downloads directory on Windows, falling back to home or cwd."""
    if sys.platform == "win32":
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            downloads = os.path.join(user_profile, "Downloads")
            if os.path.isdir(downloads) and os.access(downloads, os.W_OK):
                return downloads
    home = os.path.expanduser("~")
    downloads = os.path.join(home, "Downloads")
    if os.path.isdir(downloads) and os.access(downloads, os.W_OK):
        return downloads
    return os.getcwd()


def get_log_file_path():
    """Returns path for application log file."""
    if getattr(sys, 'frozen', False):
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if appdata:
            log_dir = os.path.join(appdata, APP_NAME)
            try:
                os.makedirs(log_dir, exist_ok=True)
                return os.path.join(log_dir, "youtubemate.log")
            except Exception:
                pass
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "youtubemate.log")
