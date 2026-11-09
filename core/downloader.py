import os
import sys
import time
import random
import re
import glob
import yt_dlp
from yt_dlp.utils import DownloadCancelled, DownloadError, ExtractorError
from utils.logging_config import logger
from config import (
    SOCKET_TIMEOUT,
    EXTRACTOR_RETRIES,
    MAX_NETWORK_RETRIES,
    INITIAL_RETRY_DELAY,
    BACKOFF_MULTIPLIER,
    HTTP_429_MAX_RETRIES,
    HTTP_429_INITIAL_DELAY,
    HTTP_429_BACKOFF_FACTOR,
    HTTP_429_MAX_DELAY,
    JITTER_RATIO,
)


class ErrorCategory:
    RATE_LIMITED = "rate_limited"
    AUTH_REQUIRED = "auth_required"
    COOKIE_DATABASE_ACCESS = "cookie_database_access"
    COOKIE_ACCESS_FAILED = COOKIE_DATABASE_ACCESS
    TRANSIENT_NETWORK = "transient_network"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


def sanitize_error_message(message):
    """Scrubs sensitive cookies, auth headers, and session tokens from error messages."""
    if not message:
        return ""
    msg_str = str(message)
    # Scrub cookie headers and known authentication tokens
    msg_str = re.sub(r'(?i)\bcookie:\s*([^\r\n;]+)', 'Cookie: [REDACTED]', msg_str)
    msg_str = re.sub(
        r'\b(__Secure-[a-zA-Z0-9_-]+|SAPISID|APISID|SSID|HSID|SID|LOGIN_INFO|VISITOR_INFO1_LIVE|PREF|GPS)=([^\s;&"\']+)',
        r'\1=[REDACTED]',
        msg_str,
    )
    return msg_str


class YTDLPLoggerAdapter:
    """Adapts yt-dlp log calls to application logger and warning handler without exposing credentials."""

    def __init__(self, warning_callback=None):
        self.warning_callback = warning_callback
        self.saw_rate_limit = False
        self.retry_after = None

    def reset_rate_limit(self):
        """Resets per-attempt rate limit tracking."""
        self.saw_rate_limit = False
        self.retry_after = None

    def debug(self, msg):
        return

    def warning(self, msg):
        clean_msg = sanitize_error_message(msg)
        if is_rate_limit_error(clean_msg):
            self.saw_rate_limit = True
            ra = parse_retry_after(clean_msg)
            if ra is not None:
                self.retry_after = ra
        if self.warning_callback:
            self.warning_callback(clean_msg)
        else:
            logger.warning("[yt-dlp] %s", clean_msg)

    def error(self, msg):
        clean_msg = sanitize_error_message(msg)
        if is_rate_limit_error(clean_msg):
            self.saw_rate_limit = True
            ra = parse_retry_after(clean_msg)
            if ra is not None:
                self.retry_after = ra
        if self.warning_callback:
            self.warning_callback(clean_msg)
        else:
            logger.error("[yt-dlp] %s", clean_msg)


def build_ydl_opts(
    js_runtime_name=None,
    js_runtime_path=None,
    ffmpeg_location=None,
    warning_callback=None,
    browser_name=None,
    logger_adapter=None,
):
    """Builds standard yt-dlp options dictionary with optimal runtime configuration and optional browser cookies."""
    logger_inst = logger_adapter if logger_adapter is not None else YTDLPLoggerAdapter(warning_callback)
    ydl_opts = {
        'quiet': True,
        'socket_timeout': SOCKET_TIMEOUT,
        'extractor_retries': EXTRACTOR_RETRIES,
        'windowsfilenames': True,
        'logger': logger_inst,
    }

    if js_runtime_name and js_runtime_path:
        ydl_opts['js_runtimes'] = {
            js_runtime_name: {
                'path': js_runtime_path,
            }
        }
        ydl_opts['remote_components'] = ['ejs:github']

    if ffmpeg_location:
        ydl_opts['ffmpeg_location'] = ffmpeg_location

    if browser_name:
        b_lower = str(browser_name).strip().lower()
        if b_lower not in ('none', 'none (unauthenticated)', 'no browser', 'off', 'false', 'null', ''):
            if "chrome" in b_lower:
                ydl_opts['cookiesfrombrowser'] = ('chrome',)
            elif "edge" in b_lower:
                ydl_opts['cookiesfrombrowser'] = ('edge',)
            elif "firefox" in b_lower:
                ydl_opts['cookiesfrombrowser'] = ('firefox',)
            elif b_lower in ('opera', 'brave', 'vivaldi', 'safari', 'chromium'):
                ydl_opts['cookiesfrombrowser'] = (b_lower,)

    return ydl_opts


def is_rate_limit_error(error_message, saw_rate_limit=False):
    """Determines whether an error is an HTTP 429 rate limit or rate-limit-induced bot challenge."""
    if not error_message:
        return False

    if saw_rate_limit and is_bot_challenge_error(error_message) and not is_restricted_content_error(error_message):
        return True

    if hasattr(error_message, 'code') and getattr(error_message, 'code') == 429:
        return True
    if hasattr(error_message, 'cause') and getattr(getattr(error_message, 'cause', None), 'code', None) == 429:
        return True
    if hasattr(error_message, 'exc_info') and error_message.exc_info:
        exc = error_message.exc_info[1] if len(error_message.exc_info) > 1 else None
        if exc and getattr(exc, 'code', None) == 429:
            return True

    msg = str(error_message).lower()
    rate_limit_keywords = [
        "http error 429",
        "<httperror 429",
        "429: too many requests",
        "429 too many requests",
        "too many requests",
        "temporarily limiting requests",
        "rate limit",
    ]
    return any(keyword in msg for keyword in rate_limit_keywords)


def is_restricted_content_error(error_message):
    """Determines whether YouTube returned an error indicating restricted content (age-gate, private, members-only)
    where authentication is genuinely necessary."""
    if not error_message:
        return False
    msg = str(error_message).lower()
    restricted_keywords = [
        "sign in to confirm your age",
        "confirm your age",
        "age-restricted",
        "private video",
        "this is a private video",
        "members-only",
        "requires payment",
        "premium",
    ]
    return any(keyword in msg for keyword in restricted_keywords)


def is_bot_challenge_error(error_message):
    """Determines whether YouTube issued an automated request challenge or bot check on a public video."""
    if not error_message:
        return False
    msg = str(error_message).lower()
    bot_keywords = [
        "confirm you're not a bot",
        "not a bot",
        "bot verification",
    ]
    return any(keyword in msg for keyword in bot_keywords)


def is_auth_required_error(error_message):
    """Determines whether YouTube requires sign-in or bot confirmation for access."""
    if not error_message:
        return False
    msg = str(error_message).lower()
    auth_keywords = [
        "sign in to confirm you're not a bot",
        "confirm you're not a bot",
        "sign in to confirm your age",
        "use --cookies-from-browser",
        "use --cookies",
        "this video requires authentication",
        "bot verification",
        "sign in to confirm",
    ]
    return any(keyword in msg for keyword in auth_keywords)


def _extract_error_chain_text(error):
    """Collects string representations from an exception and its causal/context chain."""
    if not error:
        return ""
    if isinstance(error, str):
        return error.lower()

    parts = [str(error), type(error).__name__]
    visited = set()
    curr = error
    while curr is not None and id(curr) not in visited:
        visited.add(id(curr))
        parts.append(str(curr))
        parts.append(type(curr).__name__)
        if hasattr(curr, 'exc_info') and curr.exc_info and len(curr.exc_info) > 1 and curr.exc_info[1]:
            exc = curr.exc_info[1]
            parts.append(str(exc))
            parts.append(type(exc).__name__)
        curr = getattr(curr, '__cause__', None) or getattr(curr, '__context__', None) or getattr(curr, 'cause', None)

    return " | ".join(parts).lower()


def is_cookie_access_error(error_message):
    """Determines whether browser cookies could not be accessed, copied, loaded, or decrypted."""
    if not error_message:
        return False
    msg = _extract_error_chain_text(error_message)
    cookie_error_patterns = (
        "could not copy chrome cookie database",
        "could not copy edge cookie database",
        "could not copy firefox cookie database",
        "cookie database",
        "cookies database",
        "cookies.sqlite",
        "cookieloaderror",
        "failed to load cookies",
        "could not extract cookies",
        "cannot extract cookies",
        "failed to decrypt with dpapi",
        "cannot decrypt v10 cookies",
        "cannot decrypt v11 cookies",
        "failed to decrypt cookie",
        "could not find local state file",
    )
    if any(pattern in msg for pattern in cookie_error_patterns):
        return True
    if "database is locked" in msg:
        return True
    if ("permissionerror" in msg or "permission denied" in msg or "errno 13" in msg) and (
        "cookie" in msg or "chrome" in msg or "edge" in msg or "firefox" in msg or "network\\cookies" in msg or "network/cookies" in msg
    ):
        return True
    if "cookie" in msg and ("locked" in msg or "permission denied" in msg or "keyring" in msg or "could not copy" in msg):
        return True
    return False


def is_permanent_error(error_message):
    """Determines whether a download error is permanent and should NOT be retried."""
    if not error_message:
        return False
    msg = str(error_message).lower()
    permanent_keywords = [
        "sign in to confirm",
        "private video",
        "this video is unavailable",
        "video unavailable",
        "has been removed",
        "copyright",
        "members-only",
        "account has been terminated",
        "requested format is not available",
        "unsupported url",
    ]
    return any(keyword in msg for keyword in permanent_keywords)


def is_transient_network_error(error_message):
    """Determines whether a download error is a transient network failure eligible for retry."""
    if not error_message:
        return False
    msg = str(error_message).lower()
    transient_keywords = [
        "timed out",
        "connection reset",
        "remote end closed",
        "network is unreachable",
        "temporary failure in name resolution",
        "remotedisconnected",
        "winerror 10054",
        "winerror 10060",
        "ssl: decryption_failed_or_bad_record_mac",
    ]
    return any(keyword in msg for keyword in transient_keywords)


def classify_error(error, saw_rate_limit=False):
    """Classifies an error into an ErrorCategory enum string."""
    if is_cookie_access_error(error):
        return ErrorCategory.COOKIE_DATABASE_ACCESS
    if is_rate_limit_error(error, saw_rate_limit=saw_rate_limit):
        return ErrorCategory.RATE_LIMITED
    if is_auth_required_error(error):
        return ErrorCategory.AUTH_REQUIRED
    if is_transient_network_error(error):
        return ErrorCategory.TRANSIENT_NETWORK
    if is_permanent_error(error):
        return ErrorCategory.PERMANENT
    return ErrorCategory.UNKNOWN


def parse_retry_after(error):
    """Extracts Retry-After value in seconds if present in error response headers or message."""
    if error is None:
        return None

    headers = getattr(error, 'headers', None)
    if headers is None and hasattr(error, 'cause'):
        headers = getattr(error.cause, 'headers', None)
    if headers is None and hasattr(error, 'exc_info') and error.exc_info:
        exc = error.exc_info[1] if len(error.exc_info) > 1 else None
        if exc:
            headers = getattr(exc, 'headers', None)
    if headers is None and hasattr(error, '__cause__') and error.__cause__:
        headers = getattr(error.__cause__, 'headers', None)

    if headers is not None:
        retry_val = headers.get('Retry-After') or headers.get('retry-after')
        if retry_val:
            try:
                return max(0.0, float(retry_val))
            except (ValueError, TypeError):
                try:
                    import email.utils
                    import datetime
                    dt = email.utils.parsedate_to_datetime(str(retry_val))
                    now = datetime.datetime.now(datetime.timezone.utc)
                    return max(0.0, (dt - now).total_seconds())
                except Exception:
                    pass

    msg = str(error)
    match = re.search(r'retry-after:\s*(\d+(?:\.\d+)?)', msg, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except (ValueError, TypeError):
            pass

    return None


def calculate_backoff_delay(
    attempt,
    retry_after=None,
    initial_delay=HTTP_429_INITIAL_DELAY,
    backoff_factor=HTTP_429_BACKOFF_FACTOR,
    max_delay=HTTP_429_MAX_DELAY,
    jitter_ratio=JITTER_RATIO,
):
    """Calculates bounded exponential backoff delay with jitter, respecting Retry-After."""
    if retry_after is not None and retry_after > 0:
        return min(float(retry_after), max_delay)

    base_delay = min(initial_delay * (backoff_factor ** attempt), max_delay)
    jitter = random.uniform(0.0, base_delay * jitter_ratio)
    return min(base_delay + jitter, max_delay)


def cleanup_temp_files(filepaths, retries=5, delay=0.2):
    """Removes partial temporary files after cancellation with file lock retry."""
    if not filepaths:
        return
    time.sleep(0.1)
    for filepath in list(filepaths):
        for attempt in range(retries):
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info("Removed temporary download file: %s", filepath)
                break
            except (PermissionError, OSError) as e:
                if attempt < retries - 1:
                    time.sleep(delay)
                else:
                    logger.warning("Could not remove partial file '%s' after cancellation: %s", filepath, e)
