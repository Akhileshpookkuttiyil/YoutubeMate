import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import threading
import urllib.error
import email.message
import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError

# Ensure repository root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import config
import core.downloader as dl
from core.downloader import (
    ErrorCategory,
    classify_error,
    is_rate_limit_error,
    is_auth_required_error,
    is_restricted_content_error,
    is_bot_challenge_error,
    is_cookie_access_error,
    is_permanent_error,
    is_transient_network_error,
    parse_retry_after,
    calculate_backoff_delay,
    sanitize_error_message,
    YTDLPLoggerAdapter,
)
from YoutubeMate import YouTubeDownloaderApp


class TestAuthAndRateLimit(unittest.TestCase):
    """Focused regression and unit test suite for HTTP 429, bot verification, and browser cookies."""

    def setUp(self):
        self.app = YouTubeDownloaderApp.__new__(YouTubeDownloaderApp)
        self.app.app_dir = repo_root
        self.app.output_folder = repo_root
        self.app.formats = []
        self.app.video_formats = []
        self.app.audio_formats = []
        self.app.current_video_info = None
        self.app.current_video_title = None
        self.app.current_thumbnail_url = None
        self.app._thumb_img = None
        self.app.is_fetching = False
        self.app.is_downloading = False
        self.app.is_closing = False
        self.app._state_lock = threading.Lock()
        self.app.cancel_requested = threading.Event()
        self.app.active_worker = None
        self.app.node_path = None
        self.app.js_runtime_name = None
        self.app.js_runtime_path = None
        self.app.ffmpeg_path = None
        self.app.ffmpeg_location = None
        self.app.ffmpeg_version = None
        self.app.auth_browser_value = MagicMock()
        self.app.auth_browser_value.get.return_value = config.DEFAULT_AUTH_BROWSER_DISPLAY

    # 1. Normal extraction configuration without cookies
    def test_01_normal_extraction_configuration_without_cookies(self):
        opts = dl.build_ydl_opts(browser_name=None)
        self.assertNotIn("cookiesfrombrowser", opts)

        opts_unauth = dl.build_ydl_opts(browser_name="None (Unauthenticated)")
        self.assertNotIn("cookiesfrombrowser", opts_unauth)

        # Default in app facade should be unauthenticated
        app_opts = self.app.build_ydl_opts()
        self.assertNotIn("cookiesfrombrowser", app_opts)

    # 2. Chrome cookie configuration
    def test_02_chrome_cookie_configuration(self):
        opts_short = dl.build_ydl_opts(browser_name="chrome")
        self.assertIn("cookiesfrombrowser", opts_short)
        self.assertEqual(opts_short["cookiesfrombrowser"], ("chrome",))

        opts_display = dl.build_ydl_opts(browser_name="Google Chrome")
        self.assertIn("cookiesfrombrowser", opts_display)
        self.assertEqual(opts_display["cookiesfrombrowser"], ("chrome",))

    # 3. Edge cookie configuration
    def test_03_edge_cookie_configuration(self):
        opts_short = dl.build_ydl_opts(browser_name="edge")
        self.assertIn("cookiesfrombrowser", opts_short)
        self.assertEqual(opts_short["cookiesfrombrowser"], ("edge",))

        opts_display = dl.build_ydl_opts(browser_name="Microsoft Edge")
        self.assertIn("cookiesfrombrowser", opts_display)
        self.assertEqual(opts_display["cookiesfrombrowser"], ("edge",))

    # 4. Firefox cookie configuration
    def test_04_firefox_cookie_configuration(self):
        opts_short = dl.build_ydl_opts(browser_name="firefox")
        self.assertIn("cookiesfrombrowser", opts_short)
        self.assertEqual(opts_short["cookiesfrombrowser"], ("firefox",))

        opts_display = dl.build_ydl_opts(browser_name="Firefox")
        self.assertIn("cookiesfrombrowser", opts_display)
        self.assertEqual(opts_display["cookiesfrombrowser"], ("firefox",))

    # 5. Authentication failure classification
    def test_05_auth_failure_classification(self):
        bot_msg = "ERROR: [youtube] 36sDn8S22kU: Sign in to confirm you're not a bot. Use --cookies-from-browser or --cookies for the authentication."
        self.assertTrue(is_auth_required_error(bot_msg))
        self.assertEqual(classify_error(bot_msg), ErrorCategory.AUTH_REQUIRED)

        age_gate = "ERROR: [youtube] Sign in to confirm your age"
        self.assertTrue(is_auth_required_error(age_gate))
        self.assertEqual(classify_error(age_gate), ErrorCategory.AUTH_REQUIRED)

        exc = ExtractorError("Sign in to confirm you're not a bot")
        self.assertTrue(is_auth_required_error(exc))
        self.assertEqual(classify_error(exc), ErrorCategory.AUTH_REQUIRED)

    # 6. HTTP 429 classification
    def test_06_http_429_classification(self):
        msg_429 = "Unable to download webpage: HTTP Error 429: Too Many Requests (caused by <HTTPError 429: Too Many Requests>)"
        self.assertTrue(is_rate_limit_error(msg_429))
        self.assertEqual(classify_error(msg_429), ErrorCategory.RATE_LIMITED)

        http_err = urllib.error.HTTPError("https://youtube.com", 429, "Too Many Requests", {}, None)
        self.assertTrue(is_rate_limit_error(http_err))
        self.assertEqual(classify_error(http_err), ErrorCategory.RATE_LIMITED)

        dl_err = DownloadError("HTTP Error 429: Too Many Requests", exc_info=(urllib.error.HTTPError, http_err, None))
        self.assertTrue(is_rate_limit_error(dl_err))
        self.assertEqual(classify_error(dl_err), ErrorCategory.RATE_LIMITED)

    # 7. Retry-After handling
    def test_07_retry_after_handling(self):
        # From HTTP headers
        headers = email.message.EmailMessage()
        headers["Retry-After"] = "25"
        http_err = urllib.error.HTTPError("https://youtube.com", 429, "Too Many Requests", headers, None)
        self.assertEqual(parse_retry_after(http_err), 25.0)

        # From error string
        str_err = "HTTP Error 429: Too Many Requests. Retry-After: 15"
        self.assertEqual(parse_retry_after(str_err), 15.0)

        # Backoff delay uses retry-after
        delay = calculate_backoff_delay(0, retry_after=7.5, max_delay=30.0)
        self.assertEqual(delay, 7.5)

        # Backoff delay bounds retry-after by max_delay
        bounded_delay = calculate_backoff_delay(0, retry_after=60.0, max_delay=15.0)
        self.assertEqual(bounded_delay, 15.0)

    # 8. Bounded retry behavior
    def test_08_bounded_retry_behavior(self):
        # Verify backoff without retry_after is bounded and non-negative
        d0 = calculate_backoff_delay(0, initial_delay=2.0, backoff_factor=2.0, max_delay=10.0, jitter_ratio=0.0)
        d1 = calculate_backoff_delay(1, initial_delay=2.0, backoff_factor=2.0, max_delay=10.0, jitter_ratio=0.0)
        d2 = calculate_backoff_delay(2, initial_delay=2.0, backoff_factor=2.0, max_delay=10.0, jitter_ratio=0.0)
        d3 = calculate_backoff_delay(3, initial_delay=2.0, backoff_factor=2.0, max_delay=10.0, jitter_ratio=0.0)

        self.assertEqual(d0, 2.0)
        self.assertEqual(d1, 4.0)
        self.assertEqual(d2, 8.0)
        self.assertEqual(d3, 10.0)  # Clamped by max_delay=10.0

    # 9. No retry for permanent errors
    def test_09_no_retry_for_permanent_errors(self):
        priv_msg = "ERROR: [youtube] 12345: Private video"
        self.assertEqual(classify_error(priv_msg), ErrorCategory.PERMANENT)
        self.assertTrue(is_permanent_error(priv_msg))

        unavail_msg = "ERROR: This video is unavailable"
        self.assertEqual(classify_error(unavail_msg), ErrorCategory.PERMANENT)
        self.assertTrue(is_permanent_error(unavail_msg))

        # Bot verification is not transient network error
        bot_msg = "Sign in to confirm you're not a bot"
        self.assertFalse(is_transient_network_error(bot_msg))

    # 10. No sensitive cookie information in logs
    def test_10_no_sensitive_cookie_information_in_logs(self):
        dirty_msg = "Sending Cookie: SID=supersecret123456789; HSID=supersecretpassword; __Secure-3PSID=topsecret123"
        clean_msg = sanitize_error_message(dirty_msg)
        self.assertNotIn("supersecret123456789", clean_msg)
        self.assertNotIn("supersecretpassword", clean_msg)
        self.assertNotIn("topsecret123", clean_msg)
        self.assertIn("[REDACTED]", clean_msg)

        # Test YTDLPLoggerAdapter scrubs messages
        warnings_logged = []
        adapter = YTDLPLoggerAdapter(warning_callback=lambda m: warnings_logged.append(m))
        adapter.warning("Header Cookie: SID=mysecrettoken")
        self.assertTrue(len(warnings_logged) == 1)
        self.assertNotIn("mysecrettoken", warnings_logged[0])
        self.assertIn("[REDACTED]", warnings_logged[0])

    # 11. Browser cookie access failure handling
    def test_11_browser_cookie_access_failure_handling(self):
        cookie_db_err = "FileNotFoundError: could not find chrome cookies database in 'C:\\Users\\user\\AppData\\Local\\Google\\Chrome'"
        self.assertTrue(is_cookie_access_error(cookie_db_err))
        self.assertEqual(classify_error(cookie_db_err), ErrorCategory.COOKIE_DATABASE_ACCESS)
        self.assertEqual(classify_error(cookie_db_err), ErrorCategory.COOKIE_ACCESS_FAILED)

        locked_db_err = "sqlite3.OperationalError: database is locked"
        self.assertTrue(is_cookie_access_error(locked_db_err))
        self.assertEqual(classify_error(locked_db_err), ErrorCategory.COOKIE_DATABASE_ACCESS)

        load_err = "CookieLoadError: failed to load cookies"
        self.assertTrue(is_cookie_access_error(load_err))
        self.assertEqual(classify_error(load_err), ErrorCategory.COOKIE_DATABASE_ACCESS)

    # 12. UI state restoration after extraction failure
    def test_12_ui_state_restoration_after_extraction_failure(self):
        self.app.url_entry = MagicMock()
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=test"
        self.app.ensure_js_runtime = MagicMock(return_value=True)
        self.app.set_ui_state = MagicMock()
        self.app.set_status = MagicMock()
        self.app.reset_progress = MagicMock()
        self.app.clear_metadata_preview = MagicMock()
        self.app.update_format_combo = MagicMock()
        self.app.set_format_placeholder = MagicMock()
        self.app.show_error_message = MagicMock()

        # Simulate fetch failure with rate limit
        with patch('yt_dlp.YoutubeDL') as mock_ydl_cls, \
             patch('YoutubeMate.calculate_backoff_delay', return_value=0.001):
            mock_ydl = MagicMock()
            mock_ydl.extract_info.side_effect = DownloadError("HTTP Error 429: Too Many Requests")
            mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

            # Call fetch_formats
            self.app.fetch_formats()

            # Wait for active_worker thread to complete
            if self.app.active_worker:
                self.app.active_worker.join(timeout=3.0)

            # Verification of UI state restoration
            self.assertFalse(self.app.is_fetching)
            self.assertIsNone(self.app.active_worker)
            self.app.set_ui_state.assert_called_with("idle")
            self.app.show_error_message.assert_called_with("Rate Limit Exceeded", config.MSG_RATE_LIMITED)

    # 13. Real-world Chrome cookie database PermissionError classification
    def test_13_chrome_cookie_database_permission_error(self):
        # Exact yt-dlp error message raised on Windows when Chrome locks Network\Cookies
        yt_dlp_copy_err = DownloadError(
            "ERROR: ERROR: Could not copy Chrome cookie database. See  https://github.com/yt-dlp/yt-dlp/issues/7271  for more info"
        )
        self.assertTrue(is_cookie_access_error(yt_dlp_copy_err))
        self.assertEqual(classify_error(yt_dlp_copy_err), ErrorCategory.COOKIE_DATABASE_ACCESS)
        self.assertFalse(is_rate_limit_error(yt_dlp_copy_err))
        self.assertFalse(is_auth_required_error(yt_dlp_copy_err))

        # Direct PermissionError [Errno 13] on Chrome Profile 1 Network\Cookies
        raw_perm_err = PermissionError(
            13,
            "Permission denied",
            r"C:\Users\Akhilesh\AppData\Local\Google\Chrome\User Data\Profile 1\Network\Cookies",
        )
        self.assertTrue(is_cookie_access_error(raw_perm_err))
        self.assertEqual(classify_error(raw_perm_err), ErrorCategory.COOKIE_DATABASE_ACCESS)

        # Chained exception: PermissionError -> DownloadError -> CookieLoadError -> DownloadError
        try:
            try:
                raise raw_perm_err
            except PermissionError as pe:
                raise DownloadError("ERROR: Could not copy Chrome cookie database.") from pe
        except DownloadError as de:
            chained_err = de

        self.assertTrue(is_cookie_access_error(chained_err))
        self.assertEqual(classify_error(chained_err), ErrorCategory.COOKIE_DATABASE_ACCESS)

    # 14. Edge and Firefox cookie database access failures
    def test_14_edge_and_firefox_cookie_database_access_failure(self):
        edge_perm_err = PermissionError(
            13,
            "Permission denied",
            r"C:\Users\Akhilesh\AppData\Local\Microsoft\Edge\User Data\Default\Network\Cookies",
        )
        self.assertTrue(is_cookie_access_error(edge_perm_err))
        self.assertEqual(classify_error(edge_perm_err), ErrorCategory.COOKIE_DATABASE_ACCESS)

        edge_missing_err = FileNotFoundError(
            'could not find edge cookies database in "C:\\Users\\Akhilesh\\AppData\\Local\\Microsoft\\Edge\\User Data"'
        )
        self.assertTrue(is_cookie_access_error(edge_missing_err))
        self.assertEqual(classify_error(edge_missing_err), ErrorCategory.COOKIE_DATABASE_ACCESS)

        firefox_err = FileNotFoundError(
            "could not find firefox cookies database in 'C:\\Users\\Akhilesh\\AppData\\Roaming\\Mozilla\\Firefox\\Profiles'"
        )
        self.assertTrue(is_cookie_access_error(firefox_err))
        self.assertEqual(classify_error(firefox_err), ErrorCategory.COOKIE_DATABASE_ACCESS)

        dpapi_err = DownloadError("ERROR: Failed to decrypt with DPAPI. See https://github.com/yt-dlp/yt-dlp/issues/10927")
        self.assertTrue(is_cookie_access_error(dpapi_err))
        self.assertEqual(classify_error(dpapi_err), ErrorCategory.COOKIE_DATABASE_ACCESS)

    # 15. User-friendly error message and no retries on cookie database access failure
    def test_15_cookie_access_failure_user_friendly_message_and_no_retry(self):
        # Verify browser-specific messages
        chrome_msg = config.get_cookie_access_error_message("chrome")
        self.assertEqual(
            chrome_msg,
            "Unable to access Chrome cookies. Close all Chrome windows and background processes, "
            "then try again. Alternatively, select another browser where you are signed into YouTube."
        )
        edge_msg = config.get_cookie_access_error_message("edge")
        self.assertIn("Unable to access Edge cookies. Close all Edge windows and background processes", edge_msg)
        firefox_msg = config.get_cookie_access_error_message("firefox")
        self.assertIn("Unable to access Firefox cookies. Close all Firefox windows and background processes", firefox_msg)

        # Verify fetch_formats shows friendly message, does not retry, and restores UI state
        self.app.auth_browser_value.get.return_value = "Google Chrome"
        self.app.url_entry = MagicMock()
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=36sDn8S22kU"
        self.app.ensure_js_runtime = MagicMock(return_value=True)
        self.app.set_ui_state = MagicMock()
        self.app.set_status = MagicMock()
        self.app.reset_progress = MagicMock()
        self.app.clear_metadata_preview = MagicMock()
        self.app.update_format_combo = MagicMock()
        self.app.set_format_placeholder = MagicMock()
        self.app.show_error_message = MagicMock()

        with patch('yt_dlp.YoutubeDL') as mock_ydl_cls:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.side_effect = DownloadError(
                "ERROR: ERROR: Could not copy Chrome cookie database. See  https://github.com/yt-dlp/yt-dlp/issues/7271  for more info"
            )
            mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

            self.app.fetch_formats()
            if self.app.active_worker:
                self.app.active_worker.join(timeout=3.0)

            # Must only attempt once (no retry for cookie database lock)
            self.assertEqual(mock_ydl.extract_info.call_count, 1)
            self.assertFalse(self.app.is_fetching)
            self.app.set_ui_state.assert_called_with("idle")
            self.app.show_error_message.assert_called_once_with("Cookie Access Error", chrome_msg)

    # 16. Browser selector mapping and default profile handling
    def test_16_browser_selector_and_default_profile_handling(self):
        # Verify no hardcoded Profile 1 in build_ydl_opts
        for display_name, expected_key in config.SUPPORTED_AUTH_BROWSERS:
            self.app.auth_browser_value.get.return_value = display_name
            self.assertEqual(self.app.get_selected_browser(), expected_key)
            opts = self.app.build_ydl_opts()
            if expected_key is None:
                self.assertNotIn("cookiesfrombrowser", opts)
            else:
                self.assertEqual(opts["cookiesfrombrowser"], (expected_key,))
                # Ensure tuple has length 1 (browser name only, letting yt-dlp auto-discover profile)
                self.assertEqual(len(opts["cookiesfrombrowser"]), 1)

    # 17. Anonymous extraction default and no browser variants
    def test_17_anonymous_extraction_default_and_no_browser_variants(self):
        # Default must be 'None (Unauthenticated)'
        self.assertEqual(config.DEFAULT_AUTH_BROWSER_DISPLAY, "None (Unauthenticated)")
        self.assertIsNone(config.AUTH_BROWSER_MAP["None (Unauthenticated)"])

        # Various none values must never trigger cookiesfrombrowser
        for none_val in (None, "None (Unauthenticated)", "none", "None", "", "off", "false", "no browser"):
            opts = dl.build_ydl_opts(browser_name=none_val)
            self.assertNotIn("cookiesfrombrowser", opts, f"Failed for {none_val}")

    # 18. No sign-in prompt for ordinary public videos on bot challenge
    def test_18_no_signin_prompt_for_ordinary_public_videos_on_bot_challenge(self):
        self.app.url_entry = MagicMock()
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
        self.app.ensure_js_runtime = MagicMock(return_value=True)
        self.app.set_ui_state = MagicMock()
        self.app.set_status = MagicMock()
        self.app.reset_progress = MagicMock()
        self.app.clear_metadata_preview = MagicMock()
        self.app.update_format_combo = MagicMock()
        self.app.set_format_placeholder = MagicMock()
        self.app.show_error_message = MagicMock()

        # Simulate YouTube bot challenge on a public video
        bot_err = DownloadError(
            "ERROR: [youtube] aqz-KE-bpKQ: Sign in to confirm you're not a bot. "
            "Use --cookies-from-browser or --cookies for the authentication."
        )

        with patch('yt_dlp.YoutubeDL') as mock_ydl_cls:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.side_effect = bot_err
            mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

            self.app.fetch_formats()
            if self.app.active_worker:
                self.app.active_worker.join(timeout=3.0)

            # Must NOT show authentication required sign-in prompt
            self.app.show_error_message.assert_called_once_with("Rate Limit Exceeded", config.MSG_RATE_LIMITED)
            # Placeholder should invite user to try again, NOT claim sign-in is required
            self.app.set_format_placeholder.assert_called_with("Fetch formats to try again")

    # 19. Restricted content explains optional authentication
    def test_19_restricted_content_explains_optional_authentication(self):
        self.app.url_entry = MagicMock()
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=restricted123"
        self.app.ensure_js_runtime = MagicMock(return_value=True)
        self.app.set_ui_state = MagicMock()
        self.app.set_status = MagicMock()
        self.app.reset_progress = MagicMock()
        self.app.clear_metadata_preview = MagicMock()
        self.app.update_format_combo = MagicMock()
        self.app.set_format_placeholder = MagicMock()
        self.app.show_error_message = MagicMock()

        # Simulate genuine age-gated restricted video
        age_err = DownloadError("ERROR: [youtube] Sign in to confirm your age. This video may be inappropriate for some users.")

        with patch('yt_dlp.YoutubeDL') as mock_ydl_cls:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.side_effect = age_err
            mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

            self.app.fetch_formats()
            if self.app.active_worker:
                self.app.active_worker.join(timeout=3.0)

            # For genuinely restricted content, MSG_AUTH_REQUIRED explains it
            self.app.show_error_message.assert_called_once_with("Authentication Required", config.MSG_AUTH_REQUIRED)
            self.assertIn("age-restricted, private, or members-only", config.MSG_AUTH_REQUIRED)
            self.app.set_format_placeholder.assert_called_with("Restricted content")

    # 20. HTTP 429 does not automatically switch to browser auth
    def test_20_http_429_does_not_switch_to_browser_auth(self):
        self.app.url_entry = MagicMock()
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=test429"
        self.app.ensure_js_runtime = MagicMock(return_value=True)
        self.app.set_ui_state = MagicMock()
        self.app.set_status = MagicMock()
        self.app.reset_progress = MagicMock()
        self.app.clear_metadata_preview = MagicMock()
        self.app.update_format_combo = MagicMock()
        self.app.set_format_placeholder = MagicMock()
        self.app.show_error_message = MagicMock()

        # Initial browser selection is None
        self.app.auth_browser_value = MagicMock()
        self.app.auth_browser_value.get.return_value = "None (Unauthenticated)"

        with patch('yt_dlp.YoutubeDL') as mock_ydl_cls, \
             patch('YoutubeMate.calculate_backoff_delay', return_value=0.001):
            mock_ydl = MagicMock()
            mock_ydl.extract_info.side_effect = DownloadError("HTTP Error 429: Too Many Requests")
            mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

            self.app.fetch_formats()
            if self.app.active_worker:
                self.app.active_worker.join(timeout=3.0)

            # Verify auth_browser_value.set was never called to switch to a browser
            self.app.auth_browser_value.set.assert_not_called()
            # Browser opts still do not include cookies
            self.assertIsNone(self.app.get_selected_browser())
            opts = self.app.build_ydl_opts()
            self.assertNotIn("cookiesfrombrowser", opts)

    # 21. Distinguish restricted content vs bot challenges
    def test_21_distinguish_restricted_content_vs_bot_challenges(self):
        # Restricted content keywords
        self.assertTrue(is_restricted_content_error("Sign in to confirm your age"))
        self.assertTrue(is_restricted_content_error("This video is a private video"))
        self.assertTrue(is_restricted_content_error("Join this channel to get access to members-only content"))
        self.assertFalse(is_restricted_content_error("Sign in to confirm you're not a bot"))
        self.assertFalse(is_restricted_content_error("HTTP Error 429: Too Many Requests"))

        # Bot challenge keywords
        self.assertTrue(is_bot_challenge_error("Sign in to confirm you're not a bot"))
        self.assertTrue(is_bot_challenge_error("Bot verification required"))
        self.assertFalse(is_bot_challenge_error("Sign in to confirm your age"))
        self.assertFalse(is_bot_challenge_error("This is a private video"))

    # 22. source_address is absent from default options
    def test_22_source_address_absent_from_options(self):
        opts = dl.build_ydl_opts()
        self.assertNotIn('source_address', opts)
        app_opts = self.app.build_ydl_opts()
        self.assertNotIn('source_address', app_opts)

    # 23. 429 followed by terminal bot verification is classified as RATE_LIMITED
    def test_23_429_followed_by_bot_verification_is_rate_limited(self):
        bot_msg = "ERROR: [youtube] video: Sign in to confirm you're not a bot. Use --cookies-from-browser or --cookies for the authentication."
        # Without 429 observed -> AUTH_REQUIRED
        self.assertEqual(classify_error(bot_msg, saw_rate_limit=False), ErrorCategory.AUTH_REQUIRED)
        self.assertFalse(is_rate_limit_error(bot_msg, saw_rate_limit=False))

        # With 429 observed -> RATE_LIMITED
        self.assertEqual(classify_error(bot_msg, saw_rate_limit=True), ErrorCategory.RATE_LIMITED)
        self.assertTrue(is_rate_limit_error(bot_msg, saw_rate_limit=True))

    # 24. Bot verification without an observed 429 remains AUTH_REQUIRED
    def test_24_bot_verification_without_429_remains_auth_required(self):
        bot_msg = "ERROR: [youtube] video: Sign in to confirm you're not a bot."
        adapter = YTDLPLoggerAdapter()
        # No warning logged
        self.assertFalse(adapter.saw_rate_limit)
        category = classify_error(bot_msg, saw_rate_limit=adapter.saw_rate_limit)
        self.assertEqual(category, ErrorCategory.AUTH_REQUIRED)

    # 25. Successful extraction after a 429 warning remains successful
    def test_25_successful_extraction_after_429_warning_remains_successful(self):
        adapter = YTDLPLoggerAdapter()
        adapter.warning("Unable to download webpage: HTTP Error 429: Too Many Requests")
        self.assertTrue(adapter.saw_rate_limit)

        self.app.url_entry = MagicMock()
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=mock429success"
        self.app.auth_browser_value = MagicMock()
        self.app.auth_browser_value.get.return_value = "None (Unauthenticated)"
        self.app.ensure_js_runtime = MagicMock(return_value=True)
        self.app.set_ui_state = MagicMock()
        self.app.set_status = MagicMock()
        self.app.reset_progress = MagicMock()
        self.app.clear_metadata_preview = MagicMock()
        self.app.update_format_combo = MagicMock()
        self.app.set_format_placeholder = MagicMock()
        self.app.show_error_message = MagicMock()
        self.app.update_metadata_preview = MagicMock()

        with patch('yt_dlp.YoutubeDL') as mock_ydl_cls:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = {'id': 'mock429success', 'title': 'Test Video', 'formats': []}
            mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

            self.app.fetch_formats()
            if self.app.active_worker:
                self.app.active_worker.join(timeout=3.0)

            self.assertEqual(self.app.current_video_title, "Test Video")
            self.assertFalse(self.app.is_fetching)

    # 26. 429 state is reset between attempts
    def test_26_429_state_reset_between_attempts(self):
        adapter = YTDLPLoggerAdapter()
        adapter.warning("HTTP Error 429: Too Many Requests (retry-after: 15)")
        self.assertTrue(adapter.saw_rate_limit)
        self.assertEqual(adapter.retry_after, 15.0)

        adapter.reset_rate_limit()
        self.assertFalse(adapter.saw_rate_limit)
        self.assertIsNone(adapter.retry_after)

    # 27. Separate operations do not share rate-limit state
    def test_27_separate_operations_do_not_share_state(self):
        adapter1 = YTDLPLoggerAdapter()
        adapter2 = YTDLPLoggerAdapter()

        adapter1.warning("HTTP Error 429: Too Many Requests")
        self.assertTrue(adapter1.saw_rate_limit)
        self.assertFalse(adapter2.saw_rate_limit)

    # 28. Extraction retries on 429 with bot verification and respects backoff
    def test_28_extraction_retries_on_429_with_bot_verification(self):
        self.app.url_entry = MagicMock()
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=bot429"
        self.app.auth_browser_value = MagicMock()
        self.app.auth_browser_value.get.return_value = "None (Unauthenticated)"
        self.app.ensure_js_runtime = MagicMock(return_value=True)
        self.app.set_ui_state = MagicMock()
        self.app.set_status = MagicMock()
        self.app.reset_progress = MagicMock()
        self.app.clear_metadata_preview = MagicMock()
        self.app.update_format_combo = MagicMock()
        self.app.set_format_placeholder = MagicMock()
        self.app.show_error_message = MagicMock()

        with patch('yt_dlp.YoutubeDL') as mock_ydl_cls, \
             patch('YoutubeMate.calculate_backoff_delay', return_value=0.001) as mock_backoff:

            def side_effect(url, download=False):
                ydl_opts_used = mock_ydl_cls.call_args[0][0]
                logger = ydl_opts_used.get('logger')
                if logger:
                    logger.warning("Unable to download webpage: HTTP Error 429: Too Many Requests")
                raise DownloadError("Sign in to confirm you're not a bot")

            mock_ydl = MagicMock()
            mock_ydl.extract_info.side_effect = side_effect
            mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

            self.app.fetch_formats()
            if self.app.active_worker:
                self.app.active_worker.join(timeout=3.0)

            self.assertEqual(mock_ydl.extract_info.call_count, 3)
            self.assertEqual(mock_backoff.call_count, 2)
            self.assertFalse(self.app.is_fetching)

    # 29. Anonymous mode does not load cookies
    def test_29_anonymous_mode_does_not_load_cookies(self):
        self.app.auth_browser_value = MagicMock()
        self.app.auth_browser_value.get.return_value = "None (Unauthenticated)"
        opts = self.app.build_ydl_opts()
        self.assertNotIn("cookiesfrombrowser", opts)
        self.assertNotIn("cookiefile", opts)
        self.assertIsNone(self.app.get_selected_browser())


if __name__ == "__main__":
    unittest.main()
