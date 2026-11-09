import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import threading
import tempfile
import tkinter as tk

# Ensure repository root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import config
import core.format_manager as fm
import core.ffmpeg_manager as ffm
import core.downloader as dl
import core.progress_tracker as pt
import core.metadata_manager as mm
import utils.file_utils as fu
import utils.logging_config as lc
from YoutubeMate import YouTubeDownloaderApp


class TestPriority3Config(unittest.TestCase):
    """Direct tests for config.py."""

    def test_constants_defined(self):
        self.assertEqual(config.APP_NAME, "YouTubeMate")
        self.assertEqual(config.APP_VERSION, "2.0.0")
        self.assertIn("bg", config.DARK_COLORS)
        self.assertIn("primary", config.DARK_COLORS)
        self.assertEqual(config.DARK_COLORS["primary"], "#4A6FA5")
        self.assertIn(2160, config.STANDARD_RESOLUTIONS)
        self.assertIn(1080, config.STANDARD_RESOLUTIONS)
        self.assertEqual(config.SOCKET_TIMEOUT, 30)

    def test_resource_path_resolution(self):
        base_dir = config.get_base_dir()
        self.assertTrue(os.path.isdir(base_dir))

        # Test simulated frozen PyInstaller bundle
        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, '_MEIPASS', 'C:\\fake_bundle', create=True):
            self.assertEqual(config.get_base_dir(), 'C:\\fake_bundle')
            res = config.get_resource_path("icon.ico")
            self.assertEqual(res, os.path.join('C:\\fake_bundle', 'icon.ico'))

    def test_default_download_directory(self):
        dl_dir = config.get_default_download_dir()
        self.assertTrue(os.path.isdir(dl_dir))
        self.assertTrue(os.access(dl_dir, os.W_OK))


class TestPriority3FormatManager(unittest.TestCase):
    """Direct tests for core/format_manager.py."""

    def test_safe_numeric_conversions(self):
        self.assertEqual(fm.safe_int("1080"), 1080)
        self.assertEqual(fm.safe_int(None, 42), 42)
        self.assertEqual(fm.safe_int("invalid", 0), 0)
        self.assertEqual(fm.safe_float("29.97"), 29.97)
        self.assertEqual(fm.safe_float(None, 0.0), 0.0)

    def test_format_filesize(self):
        self.assertEqual(fm.format_filesize(0), "")
        self.assertEqual(fm.format_filesize(500), "500 B")
        self.assertEqual(fm.format_filesize(1500), "1.5 KB")
        self.assertEqual(fm.format_filesize(1048576 * 5), "5.0 MB")
        self.assertEqual(fm.format_filesize(1073741824 * 2), "2.00 GB")

    def test_is_valid_format_validation(self):
        self.assertFalse(fm.is_valid_format(None))
        self.assertFalse(fm.is_valid_format({}))
        self.assertFalse(fm.is_valid_format({'format_id': 'sb0', 'format_note': 'storyboard'}))
        self.assertFalse(fm.is_valid_format({'format_id': '1', 'ext': 'mhtml'}))
        self.assertFalse(fm.is_valid_format({'format_id': '1', 'vcodec': 'none', 'height': 720}))
        self.assertFalse(fm.is_valid_format({'format_id': '1', 'vcodec': 'avc1', 'height': 0}))
        self.assertTrue(fm.is_valid_format({'format_id': '18', 'vcodec': 'avc1', 'height': 360, 'ext': 'mp4'}))

    def test_is_valid_audio_format_validation(self):
        self.assertFalse(fm.is_valid_audio_format({'format_id': '18', 'vcodec': 'avc1', 'acodec': 'mp4a'}))
        self.assertFalse(fm.is_valid_audio_format({'format_id': '1', 'vcodec': 'none', 'acodec': 'none'}))
        self.assertTrue(fm.is_valid_audio_format({'format_id': '140', 'vcodec': 'none', 'acodec': 'mp4a', 'ext': 'm4a'}))

    def test_resolution_label_generation(self):
        self.assertEqual(fm.format_resolution_label(2160), "2160p (4K)")
        self.assertEqual(fm.format_resolution_label(1440), "1440p (2K)")
        self.assertEqual(fm.format_resolution_label(1080), "1080p (Full HD)")
        self.assertEqual(fm.format_resolution_label(720), "720p (HD)")
        self.assertEqual(fm.format_resolution_label(480), "480p (SD)")
        self.assertEqual(fm.format_resolution_label(360), "360p")
        self.assertEqual(fm.format_resolution_label(240), "240p")
        self.assertEqual(fm.format_resolution_label(144), "144p")
        self.assertEqual(fm.format_resolution_label(0), "?p")
        self.assertEqual(fm.format_resolution_label(None), "?p")

    def test_format_candidate_tiering_and_deduplication(self):
        raw_info = {
            'formats': [
                {'format_id': '137', 'vcodec': 'avc1', 'acodec': 'none', 'height': 1080, 'ext': 'mp4', 'fps': 30, 'tbr': 4000},
                {'format_id': '248', 'vcodec': 'vp9', 'acodec': 'none', 'height': 1080, 'ext': 'webm', 'fps': 30, 'tbr': 3000},
                {'format_id': '18', 'vcodec': 'avc1', 'acodec': 'mp4a', 'height': 360, 'ext': 'mp4', 'fps': 30, 'tbr': 600},
            ]
        }
        candidates = fm.get_format_candidates(raw_info)
        fids = [c[0]['format_id'] for c in candidates]
        # Should pick best 1080p adaptive (137) and 360p progressive (18)
        self.assertIn('137', fids)
        self.assertIn('18', fids)
        # Verify deduplication within tier
        self.assertEqual(fids.count('137'), 1)

    def test_audio_candidates_m4a_and_mp3(self):
        raw_info = {
            'formats': [
                {'format_id': '140', 'vcodec': 'none', 'acodec': 'mp4a.40.2', 'ext': 'm4a', 'abr': 128, 'filesize': 300000},
                {'format_id': '251', 'vcodec': 'none', 'acodec': 'opus', 'ext': 'webm', 'abr': 160, 'filesize': 350000},
            ]
        }
        audio_cands = fm.get_audio_candidates(raw_info, ffmpeg_location=None)
        # Must include Best M4A (no FFmpeg), Best MP3 (needs FFmpeg), and valid audio streams
        m4a_entry = next((c for c in audio_cands if c[5] == 'm4a'), None)
        mp3_entry = next((c for c in audio_cands if c[5] == 'mp3'), None)
        self.assertIsNotNone(m4a_entry)
        self.assertEqual(m4a_entry[1], '140')
        self.assertIn("No FFmpeg", m4a_entry[0])
        self.assertIsNotNone(mp3_entry)
        self.assertIn("needs FFmpeg", mp3_entry[0])


class TestPriority3FFmpegManager(unittest.TestCase):
    """Direct tests for core/ffmpeg_manager.py."""

    @patch('shutil.which')
    @patch('os.path.isfile')
    @patch('os.access')
    def test_executable_discovery(self, mock_access, mock_isfile, mock_which):
        mock_access.return_value = True
        mock_isfile.side_effect = lambda path: bool(path and path.endswith("ffmpeg.exe"))
        mock_which.return_value = "C:\\tools\\ffmpeg.exe"

        found = ffm.find_executable("ffmpeg", app_dir="C:\\app")
        self.assertIsNotNone(found)
        self.assertTrue(found.endswith("ffmpeg.exe"))

    @patch('subprocess.run')
    @patch('os.path.isfile')
    def test_validate_ffmpeg_executable(self, mock_isfile, mock_run):
        mock_isfile.return_value = True

        # Valid execution
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = "ffmpeg version 7.1-full_build Copyright (c) 2000-2024"
        mock_run.return_value = proc
        ver = ffm.validate_ffmpeg_executable("C:\\ffmpeg.exe")
        self.assertEqual(ver, "7.1-full_build")

        # Invalid execution
        proc.returncode = 1
        ver_fail = ffm.validate_ffmpeg_executable("C:\\ffmpeg.exe")
        self.assertIsNone(ver_fail)

    @patch('shutil.which', return_value=None)
    def test_missing_ffmpeg_returns_none(self, mock_which):
        path, ver = ffm.find_ffmpeg(app_dir="C:\\empty_dir")
        self.assertIsNone(path)
        self.assertIsNone(ver)

    @patch.object(ffm, 'find_executable')
    @patch.object(ffm, 'find_ffmpeg')
    def test_detect_dependencies(self, mock_find_ff, mock_find_exe):
        mock_find_exe.side_effect = lambda name, app_dir=None: "C:\\node.exe" if name == "node" else None
        mock_find_ff.return_value = ("C:\\ffmpeg\\bin\\ffmpeg.exe", "7.1")

        deps = ffm.detect_dependencies()
        self.assertEqual(deps["node_path"], "C:\\node.exe")
        self.assertEqual(deps["js_runtime_name"], "node")
        self.assertEqual(deps["ffmpeg_version"], "7.1")
        self.assertEqual(deps["ffmpeg_location"], "C:\\ffmpeg\\bin")


class TestPriority3Downloader(unittest.TestCase):
    """Direct tests for core/downloader.py."""

    def test_build_ydl_opts(self):
        opts = dl.build_ydl_opts(
            js_runtime_name="node",
            js_runtime_path="C:\\node.exe",
            ffmpeg_location="C:\\ffmpeg",
        )
        self.assertTrue(opts['quiet'])
        self.assertEqual(opts['socket_timeout'], 30)
        self.assertEqual(opts['ffmpeg_location'], "C:\\ffmpeg")
        self.assertIn("node", opts['js_runtimes'])
        self.assertEqual(opts['js_runtimes']['node']['path'], "C:\\node.exe")

    def test_permanent_error_classification(self):
        self.assertTrue(dl.is_permanent_error("ERROR: [youtube] video: Private video"))
        self.assertTrue(dl.is_permanent_error("ERROR: This video is unavailable"))
        self.assertTrue(dl.is_permanent_error("Sign in to confirm you're not a bot"))
        self.assertFalse(dl.is_permanent_error("socket.timeout: The read operation timed out"))

    def test_transient_error_classification(self):
        self.assertTrue(dl.is_transient_network_error("urllib.error.URLError: <urlopen error timed out>"))
        self.assertTrue(dl.is_transient_network_error("Connection reset by peer"))
        self.assertTrue(dl.is_transient_network_error("WinError 10054"))
        self.assertFalse(dl.is_transient_network_error("ERROR: Private video"))

    def test_cleanup_temp_files(self):
        with tempfile.TemporaryDirectory() as td:
            f1 = os.path.join(td, "test.part")
            f2 = os.path.join(td, "test.ytdl")
            with open(f1, 'w') as f:
                f.write("partial")
            with open(f2, 'w') as f:
                f.write("metadata")
            self.assertTrue(os.path.exists(f1))
            self.assertTrue(os.path.exists(f2))

            dl.cleanup_temp_files([f1, f2], retries=2, delay=0.01)
            self.assertFalse(os.path.exists(f1))
            self.assertFalse(os.path.exists(f2))


class TestPriority3ProgressTracker(unittest.TestCase):
    """Direct tests for core/progress_tracker.py."""

    def test_progress_monotonicity(self):
        updates = []
        tracker = pt.DownloadProgressTracker(requires_merge=False, on_progress=lambda p, e, s, t: updates.append(p))

        # Feed non-monotonic raw values (e.g. fragment retry)
        tracker.hook({'status': 'downloading', 'downloaded_bytes': 500, 'total_bytes': 1000})
        tracker.hook({'status': 'downloading', 'downloaded_bytes': 300, 'total_bytes': 1000})
        tracker.hook({'status': 'downloading', 'downloaded_bytes': 800, 'total_bytes': 1000})

        # All recorded values must be monotonically increasing or equal
        for i in range(len(updates) - 1):
            self.assertGreaterEqual(updates[i + 1], updates[i])

    def test_unknown_filesize_handling(self):
        stages = []
        tracker = pt.DownloadProgressTracker(requires_merge=False, on_progress=lambda p, e, s, t: stages.append(t))
        tracker.hook({'status': 'downloading', 'downloaded_bytes': 10485760, 'total_bytes': None})
        self.assertTrue(any("10.0 MB downloaded" in s for s in stages))

    def test_stage_transitions_adaptive(self):
        percentages = []
        tracker = pt.DownloadProgressTracker(requires_merge=True, on_progress=lambda p, e, s, t: percentages.append(p))

        # Stage 1: Video
        tracker.hook({'status': 'downloading', 'filename': 'vid.mp4', 'downloaded_bytes': 500, 'total_bytes': 1000})
        # Video finished
        tracker.hook({'status': 'finished'})
        self.assertGreaterEqual(tracker.last_percent, 85.0)

        # Stage 2: Audio
        tracker.hook({'status': 'downloading', 'filename': 'aud.m4a', 'downloaded_bytes': 500, 'total_bytes': 1000})
        self.assertEqual(tracker.current_stage, 2)


class TestPriority3MetadataManager(unittest.TestCase):
    """Direct tests for core/metadata_manager.py."""

    def test_format_duration(self):
        self.assertEqual(mm.format_duration(None), "")
        self.assertEqual(mm.format_duration(0), "")
        self.assertEqual(mm.format_duration(45), "00:45")
        self.assertEqual(mm.format_duration(215), "03:35")
        self.assertEqual(mm.format_duration(3665), "1:01:05")

    def test_format_view_count(self):
        self.assertEqual(mm.format_view_count(None), "")
        self.assertEqual(mm.format_view_count(500), "500 views")
        self.assertEqual(mm.format_view_count(1500), "1.5K views")
        self.assertEqual(mm.format_view_count(2500000), "2.5M views")
        self.assertEqual(mm.format_view_count(1200000000), "1.2B views")

    def test_thumbnail_error_handling(self):
        # Invalid / unreachable URL must return (None, None) gracefully without raising exception
        pil_img, out_path = mm.download_and_process_thumbnail("http://invalid.unreachable.domain/thumb.jpg")
        self.assertIsNone(pil_img)
        self.assertIsNone(out_path)


class TestPriority3FileUtils(unittest.TestCase):
    """Direct tests for utils/file_utils.py."""

    def test_filename_sanitization(self):
        self.assertEqual(fu.sanitize_filename(""), "video")
        self.assertEqual(fu.sanitize_filename(None), "video")
        self.assertEqual(fu.sanitize_filename('Bad/Name: *With? <Illegal> "Chars"|'), "Bad_Name_ _With_ _Illegal_ _Chars__")
        self.assertEqual(fu.sanitize_filename("Trailing dot..."), "Trailing dot")
        self.assertEqual(fu.sanitize_filename("CON"), "_CON")
        self.assertEqual(fu.sanitize_filename("prn"), "_prn")
        self.assertEqual(fu.sanitize_filename("100% Tutorial"), "100% Tutorial")

    def test_unique_filename_collision(self):
        with tempfile.TemporaryDirectory() as td:
            base1 = fu.get_unique_filename(td, "Video", "mp4")
            self.assertEqual(base1, "Video")

            # Create file
            with open(os.path.join(td, "Video.mp4"), 'w') as f:
                f.write("data")

            base2 = fu.get_unique_filename(td, "Video", "mp4")
            self.assertEqual(base2, "Video (1)")

            with open(os.path.join(td, "Video (1).mp4"), 'w') as f:
                f.write("data")

            base3 = fu.get_unique_filename(td, "Video", "mp4")
            self.assertEqual(base3, "Video (2)")

    @patch('sys.platform', 'win32')
    @patch('os.startfile', create=True)
    def test_open_folder_windows(self, mock_startfile):
        with tempfile.TemporaryDirectory() as td:
            res = fu.open_folder(td)
            self.assertTrue(res)
            mock_startfile.assert_called_once_with(os.path.abspath(td))


class TestPriority3ArchitectureCorrections(unittest.TestCase):
    """Verifies that separate application instances have independent locks and cancellation events."""

    def test_independent_locks_and_events_regular_instantiation(self):
        root1 = MagicMock()
        root2 = MagicMock()

        # Regular instantiation via __init__
        app1 = YouTubeDownloaderApp.__new__(YouTubeDownloaderApp)
        app1.root = root1
        app1.__init__(root1)

        app2 = YouTubeDownloaderApp.__new__(YouTubeDownloaderApp)
        app2.root = root2
        app2.__init__(root2)

        # Locks and cancellation events must be distinct objects
        self.assertIsNot(app1._state_lock, app2._state_lock)
        self.assertIsNot(app1.cancel_requested, app2.cancel_requested)

        # Mutating cancel state on app1 must NOT affect app2
        app1.cancel_requested.set()
        self.assertTrue(app1.cancel_requested.is_set())
        self.assertFalse(app2.cancel_requested.is_set())

    def test_independent_locks_and_events_headless_new_instantiation(self):
        # Legacy headless instantiation via __new__ without __init__
        app1 = YouTubeDownloaderApp.__new__(YouTubeDownloaderApp)
        app2 = YouTubeDownloaderApp.__new__(YouTubeDownloaderApp)

        lock1 = app1._state_lock
        lock2 = app2._state_lock

        # Distinct locks
        self.assertIsNot(lock1, lock2)
        # Same instance must return the identical cached lock
        self.assertIs(app1._state_lock, lock1)
        self.assertIs(app2._state_lock, lock2)

        event1 = app1.cancel_requested
        event2 = app2.cancel_requested

        # Distinct cancellation events
        self.assertIsNot(event1, event2)
        app1.cancel_requested.set()
        self.assertTrue(app1.cancel_requested.is_set())
        self.assertFalse(app2.cancel_requested.is_set())


class TestPriority3LifecycleShutdownSafety(unittest.TestCase):
    """Verifies that UI callbacks are safely protected during and after shutdown."""

    def setUp(self):
        self.mock_root = MagicMock()
        self.app = YouTubeDownloaderApp.__new__(YouTubeDownloaderApp)
        self.app.root = self.mock_root
        self.app.is_closing = False

    def test_callback_not_scheduled_when_closing(self):
        self.app.is_closing = True
        mock_cb = MagicMock()

        with patch('threading.current_thread') as mock_thread, \
             patch('threading.main_thread') as mock_main:
            mock_thread.return_value = "WorkerThread"
            mock_main.return_value = "MainThread"

            self.app.run_on_ui_thread(mock_cb)
            # Must NOT schedule via root.after when is_closing is True
            self.mock_root.after.assert_not_called()
            mock_cb.assert_not_called()

    def test_already_scheduled_callback_handles_destroyed_window(self):
        mock_cb = MagicMock(side_effect=tk.TclError("invalid command name"))

        # When callback runs, if Tkinter throws TclError (widget destroyed), it is safely suppressed
        try:
            self.app.run_on_ui_thread(mock_cb)
        except tk.TclError:
            self.fail("run_on_ui_thread raised unhandled tk.TclError during widget teardown")

    def test_destroy_root_marks_is_closing(self):
        self.app._destroy_root()
        self.assertTrue(self.app.is_closing)
        self.mock_root.destroy.assert_called_once()


if __name__ == '__main__':
    unittest.main()
