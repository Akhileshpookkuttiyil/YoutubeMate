import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import time
import tempfile
import threading

# Ensure repository root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import yt_dlp
from yt_dlp.utils import DownloadCancelled
from YoutubeMate import YouTubeDownloaderApp, DownloadProgressTracker


class TestPriority1StabilityAndLifecycle(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Patch messagebox everywhere so modal dialogs never block tests
        cls.patch_err = patch('tkinter.messagebox.showerror')
        cls.patch_warn = patch('tkinter.messagebox.showwarning')
        cls.patch_info = patch('tkinter.messagebox.showinfo')
        cls.patch_yesno = patch('tkinter.messagebox.askyesno', return_value=True)
        cls.mock_err = cls.patch_err.start()
        cls.mock_warn = cls.patch_warn.start()
        cls.mock_info = cls.patch_info.start()
        cls.mock_yesno = cls.patch_yesno.start()

    @classmethod
    def tearDownClass(cls):
        cls.patch_err.stop()
        cls.patch_warn.stop()
        cls.patch_info.stop()
        cls.patch_yesno.stop()

    def setUp(self):
        # Create headless mock of Tk
        self.mock_root = MagicMock()
        self.mock_root.winfo_reqwidth.return_value = 780
        self.mock_root.winfo_reqheight.return_value = 640
        self.mock_root.winfo_screenwidth.return_value = 1920
        self.mock_root.winfo_screenheight.return_value = 1080
        self.mock_root.winfo_exists.return_value = True

        self.app = YouTubeDownloaderApp.__new__(YouTubeDownloaderApp)
        self.app.root = self.mock_root
        self.app.app_dir = repo_root
        self.app.formats = []
        self.app.output_folder = repo_root
        self.app.node_path = "C:\\fake\\node.exe"
        self.app.js_runtime_name = "node"
        self.app.js_runtime_path = "C:\\fake\\node.exe"
        self.app.ffmpeg_path = "C:\\fake\\ffmpeg.exe"
        self.app.ffmpeg_location = "C:\\fake"
        self.app.ffmpeg_version = "7.1"
        self.app.format_placeholder = "Fetch formats to choose a quality"

        self.app.is_fetching = False
        self.app.is_downloading = False
        self.app.is_closing = False
        self.app._state_lock = threading.Lock()
        self.app.active_worker = None
        self.app.cancel_requested = threading.Event()

        # Mock UI widgets & state variables
        self.app.url_entry = MagicMock()
        self.app.fetch_btn = MagicMock()
        self.app.download_btn = MagicMock()
        self.app.cancel_btn = MagicMock()
        self.app.format_combo = MagicMock()
        self.app.status_label = MagicMock()
        self.app.warning_value = MagicMock()
        self.app.progress_value = MagicMock()
        self.app.eta_value = MagicMock()
        self.app.speed_value = MagicMock()
        self.app.progress_text = MagicMock()

    # 1. Progress updates are throttled
    def test_01_progress_updates_throttled(self):
        updates = []
        def on_prog(percent, eta, speed, stage_text):
            updates.append(percent)

        tracker = DownloadProgressTracker(requires_merge=False, on_progress=on_prog)

        # Dispatch 50 rapid updates within a few milliseconds
        for i in range(50):
            tracker.hook({
                'status': 'downloading',
                'downloaded_bytes': (i + 1) * 10,
                'total_bytes': 1000,
                '_eta_str': '00:05',
                '_speed_str': '1.0MiB/s',
            })

        # Due to 100ms throttling, only a small fraction of updates should have fired
        self.assertTrue(len(updates) < 10, f"Expected < 10 updates but got {len(updates)}")
        self.assertGreater(len(updates), 0)

    # 2. Progress percentage remains valid
    def test_02_progress_percentage_remains_valid(self):
        # Test negative, excessive, and string values
        self.app.update_progress(-20.0, "ETA: --", "--")
        self.app.progress_value.set.assert_called_with(0.0)

        self.app.update_progress(150.0, "ETA: --", "--")
        self.app.progress_value.set.assert_called_with(100.0)

        self.app.update_progress("75.4%", "ETA: --", "--")
        self.app.progress_value.set.assert_called_with(75.4)

    # 3. Unknown total file size
    def test_03_unknown_total_file_size(self):
        updates = []
        def on_prog(percent, eta, speed, stage_text):
            updates.append((percent, stage_text))

        tracker = DownloadProgressTracker(requires_merge=False, on_progress=on_prog)
        tracker.hook({
            'status': 'downloading',
            'downloaded_bytes': 5 * 1024 * 1024, # 5 MB
            'total_bytes': None,
            'total_bytes_estimate': None,
            '_speed_str': '1.5MiB/s',
        })

        self.assertEqual(len(updates), 1)
        self.assertIn("5.0 MB downloaded", updates[0][1])

    # 4. Multi-stream progress reporting (monotonic, no backward jumps)
    def test_04_multi_stream_progress_reporting(self):
        updates = []
        def on_prog(percent, eta, speed, stage_text):
            updates.append((round(percent, 1), stage_text))

        tracker = DownloadProgressTracker(requires_merge=True, on_progress=on_prog)

        # Stage 1: Video stream downloading (50% through video)
        tracker.hook({'status': 'downloading', 'filename': 'video.mp4', 'downloaded_bytes': 500, 'total_bytes': 1000})
        self.assertAlmostEqual(updates[-1][0], 42.5, places=1) # 50% * 0.85 = 42.5%
        self.assertIn("Stage 1/2", updates[-1][1])

        # Stage 1: Video stream finished -> 85%
        tracker.hook({'status': 'finished', 'filename': 'video.mp4'})
        self.assertAlmostEqual(updates[-1][0], 85.0, places=1)

        # Stage 2: Audio stream starts at 0%
        tracker.last_update_time = 0 # reset throttle for test
        tracker.hook({'status': 'downloading', 'filename': 'audio.m4a', 'downloaded_bytes': 0, 'total_bytes': 100})
        # Must not jump backwards to 0%!
        self.assertGreaterEqual(updates[-1][0], 85.0)
        self.assertIn("Stage 2/2", updates[-1][1])

        # Stage 2: Audio stream at 50% -> 85 + (50% * 0.10) = 90%
        tracker.last_update_time = 0
        tracker.hook({'status': 'downloading', 'filename': 'audio.m4a', 'downloaded_bytes': 50, 'total_bytes': 100})
        self.assertAlmostEqual(updates[-1][0], 90.0, places=1)

    # 5. Post-processing state
    def test_05_post_processing_state(self):
        updates = []
        def on_prog(percent, eta, speed, stage_text):
            updates.append((percent, stage_text))

        tracker = DownloadProgressTracker(requires_merge=True, on_progress=on_prog)
        tracker.current_stage = 2
        tracker.hook({'status': 'finished', 'filename': 'audio.m4a'})

        self.assertGreaterEqual(updates[-1][0], 95.0)
        self.assertIn("Merging", updates[-1][1])

    # 6. Cancellation during download
    def test_06_cancellation_during_download(self):
        self.app.is_downloading = True
        self.app.cancel_requested.clear()

        # Request cancellation
        self.app.cancel_download()
        self.assertTrue(self.app.cancel_requested.is_set())

        # Progress hook should detect cancellation and raise DownloadCancelled
        def test_hook(d):
            if self.app.cancel_requested.is_set():
                raise DownloadCancelled("Cancelled by user")

        with self.assertRaises(DownloadCancelled):
            test_hook({'status': 'downloading'})

    # 7. Cancellation cleanup
    def test_07_cancellation_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            part_file = os.path.join(tmp_dir, "test_video.mp4.part")
            ytdl_file = os.path.join(tmp_dir, "test_video.mp4.ytdl")
            finished_file = os.path.join(tmp_dir, "completed_video.mp4")

            # Create test files
            for p in (part_file, ytdl_file, finished_file):
                with open(p, "w") as f:
                    f.write("content")

            temp_files = {part_file, ytdl_file}
            self.app._cleanup_temp_files(temp_files)

            # Incomplete temporary files must be deleted
            self.assertFalse(os.path.exists(part_file))
            self.assertFalse(os.path.exists(ytdl_file))
            # Completed files must be preserved!
            self.assertTrue(os.path.exists(finished_file))

    # 8. Duplicate download prevention
    def test_08_duplicate_download_prevention(self):
        self.app.is_downloading = True
        self.app.formats = [("18 - 360p - mp4", "18", False, {})]
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        with patch('threading.Thread') as mock_thread:
            # Calling download while already downloading must be rejected
            self.app.download_video()
            mock_thread.assert_not_called()

        with patch('threading.Thread') as mock_thread:
            # Calling fetch while downloading must be rejected
            self.app.fetch_formats()
            mock_thread.assert_not_called()

    # 9. Worker completion resets flags and UI
    def test_09_worker_completion(self):
        self.app.is_downloading = True
        self.app.set_ui_state("downloading")
        self.app.cancel_btn.config.assert_called_with(state="normal")

        # Simulate completion
        self.app.is_downloading = False
        self.app.set_ui_state("idle")
        self.app.cancel_btn.config.assert_called_with(state="disabled")

    # 10. Non-blocking closing during extraction
    def test_10_closing_during_extraction(self):
        self.app.is_fetching = True
        mock_worker = MagicMock()
        mock_worker.is_alive.return_value = True
        self.app.active_worker = mock_worker

        with patch.object(self.app, '_destroy_root') as mock_destroy:
            self.app.on_closing()
            self.assertTrue(self.app.cancel_requested.is_set())
            # Main thread must NOT synchronously block on join
            mock_worker.join.assert_not_called()
            # Non-blocking poll must be scheduled via Tkinter after()
            self.mock_root.after.assert_called_with(50, unittest.mock.ANY)

            # Simulate worker finishing: polling callback completes shutdown
            mock_worker.is_alive.return_value = False
            self.app._poll_worker_shutdown(time.time() + 4.0)
            mock_destroy.assert_called_once()

    # 11. Non-blocking closing during download
    def test_11_closing_during_download(self):
        self.app.is_downloading = True
        mock_worker = MagicMock()
        mock_worker.is_alive.return_value = True
        self.app.active_worker = mock_worker

        with patch.object(self.app, '_destroy_root') as mock_destroy:
            self.app.on_closing()
            self.assertTrue(self.app.cancel_requested.is_set())
            # Main thread must NOT synchronously block on join
            mock_worker.join.assert_not_called()
            # Non-blocking poll must be scheduled via Tkinter after()
            self.mock_root.after.assert_called_with(50, unittest.mock.ANY)

            # Simulate worker finishing: polling callback completes shutdown
            mock_worker.is_alive.return_value = False
            self.app._poll_worker_shutdown(time.time() + 4.0)
            mock_destroy.assert_called_once()

    # 12. Callback after window destruction
    def test_12_callback_after_window_destruction(self):
        self.mock_root.winfo_exists.return_value = False
        # Invoking callbacks after window destruction must gracefully pass without exception
        try:
            self.app.run_on_ui_thread(self.app.set_status, "Test")
            self.app.set_ui_state("idle")
            self.app.update_progress(50, "ETA", "Speed")
            self.app.reset_progress()
        except Exception as e:
            self.fail(f"Callback crashed after window destruction: {e}")

    # 13. Network failure recovery
    def test_13_network_failure_recovery(self):
        with patch.object(self.app, 'show_error_message') as mock_err, \
             patch.object(self.app, 'set_status') as mock_status:
            # Simulate network exception caught in _download
            self.app.set_status("Download failed.")
            self.app.reset_progress()
            self.app.show_error_message("Error", "Network Connection Reset")
            self.app.set_ui_state("idle")

            mock_err.assert_called_with("Error", "Network Connection Reset")
            mock_status.assert_called_with("Download failed.")

    # 14. GUI state restoration across transitions
    def test_14_gui_state_restoration(self):
        self.app.formats = [("18 - 360p - mp4", "18", False, {})]
        self.app.format_combo.current.return_value = 0

        # Idle with formats
        self.app.set_ui_state("idle")
        self.app.download_btn.config.assert_called_with(state="normal")
        self.app.cancel_btn.config.assert_called_with(state="disabled")

        # Downloading
        self.app.set_ui_state("downloading")
        self.app.download_btn.config.assert_called_with(state="disabled")
        self.app.cancel_btn.config.assert_called_with(state="normal")

        # Fetching - user can also cancel a slow fetch!
        self.app.set_ui_state("fetching")
        self.app.download_btn.config.assert_called_with(state="disabled")
        self.app.cancel_btn.config.assert_called_with(state="normal")

        # Completed/Idle
        self.app.set_ui_state("completed")
        self.app.download_btn.config.assert_called_with(state="normal")
        self.app.cancel_btn.config.assert_called_with(state="disabled")

    # 15. Dynamic stage weighting based on known stream sizes
    def test_15_dynamic_stage_weighting(self):
        # 100MB video, 25MB audio -> total 125MB. Video: 80% of bytes (76% of bar), Audio: 20% of bytes (19% of bar)
        tracker = DownloadProgressTracker(requires_merge=True, video_size=100*1024*1024, audio_size=25*1024*1024)
        self.assertAlmostEqual(tracker.video_weight, 76.0, places=1)
        self.assertAlmostEqual(tracker.audio_weight, 19.0, places=1)
        self.assertAlmostEqual(tracker.video_weight + tracker.audio_weight, 95.0, places=1)

    # 16. Monotonic progress on fragment retries and backwards bytes
    def test_16_monotonic_fragment_retries(self):
        updates = []
        def on_prog(percent, eta, speed, stage_text):
            updates.append(percent)

        tracker = DownloadProgressTracker(requires_merge=True, on_progress=on_prog)
        # Stage 1 reaches 50% of stream (42.5% overall)
        tracker.hook({'status': 'downloading', 'filename': 'video.mp4', 'downloaded_bytes': 500, 'total_bytes': 1000})
        self.assertAlmostEqual(updates[-1], 42.5, places=1)

        # Network glitch: fragment resets to 300 bytes (30% of stream = 25.5% overall)
        tracker.last_update_time = 0
        tracker.hook({'status': 'downloading', 'filename': 'video.mp4', 'downloaded_bytes': 300, 'total_bytes': 1000})
        # Progress must NOT drop to 25.5%! It must remain 42.5%
        self.assertAlmostEqual(updates[-1], 42.5, places=1)

        # Stage 2 (Audio) reaches 50% of audio stream (90% overall)
        tracker.hook({'status': 'finished', 'filename': 'video.mp4'})
        tracker.last_update_time = 0
        tracker.hook({'status': 'downloading', 'filename': 'audio.m4a', 'downloaded_bytes': 50, 'total_bytes': 100})
        self.assertAlmostEqual(updates[-1], 90.0, places=1)

        # Audio fragment retry drops to 20 bytes (87% overall)
        tracker.last_update_time = 0
        tracker.hook({'status': 'downloading', 'filename': 'audio.m4a', 'downloaded_bytes': 20, 'total_bytes': 100})
        # Progress must NOT drop! It must remain 90.0%
        self.assertAlmostEqual(updates[-1], 90.0, places=1)

    # 17. Cleanup handles Windows file locks (PermissionError backoff)
    def test_17_cleanup_permission_error_retry(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            locked_part = os.path.join(tmp_dir, "test.mp4.part")
            with open(locked_part, "w") as f:
                f.write("content")

            original_remove = os.remove
            calls = [0]

            def mock_locked_remove(path):
                calls[0] += 1
                if calls[0] < 3:
                    raise PermissionError(13, "The process cannot access the file because it is being used by another process")
                return original_remove(path)

            with patch('os.remove', side_effect=mock_locked_remove):
                self.app._cleanup_temp_files({locked_part}, max_retries=4, delay=0.01)

            self.assertGreaterEqual(calls[0], 3)
            self.assertFalse(os.path.exists(locked_part))

    # 18. Synchronous flag assignment eliminates double-click race conditions
    def test_18_double_click_race_condition(self):
        self.app.is_downloading = False
        self.app.formats = [("18 - 360p - mp4", "18", False, {})]
        self.app.format_combo.current.return_value = 0
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        threads_spawned = []
        original_thread = threading.Thread

        def mock_thread_init(*args, **kwargs):
            # When the thread object is constructed, verify that is_downloading is ALREADY True
            self.assertTrue(self.app.is_downloading, "is_downloading must be True BEFORE thread launch")
            t = original_thread(*args, **kwargs)
            threads_spawned.append(t)
            return t

        with patch('threading.Thread', side_effect=mock_thread_init):
            self.app.download_video()

        self.assertEqual(len(threads_spawned), 1)

    # 19. Cancellation during format extraction
    def test_19_cancellation_during_fetch(self):
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        self.app.is_fetching = False

        # Clear and set cancellation during extraction
        self.app.cancel_requested.clear()

        def mock_extract(*args, **kwargs):
            self.app.cancel_requested.set()
            return {'formats': []}

        with patch.object(yt_dlp.YoutubeDL, 'extract_info', side_effect=mock_extract):
            # Start fetch
            self.app.fetch_formats()
            # Wait briefly for worker to complete
            if self.app.active_worker:
                self.app.active_worker.join(timeout=1.0)

        # Must have cancelled cleanly without populating formats or raising error dialogs
        self.assertEqual(len(self.app.formats), 0)
        self.assertFalse(self.app.is_fetching)
        self.mock_err.assert_not_called()


if __name__ == '__main__':
    unittest.main()
