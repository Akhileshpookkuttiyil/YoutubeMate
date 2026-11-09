import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import threading
import queue
import tkinter as tk

# Ensure repository root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import config
from YoutubeMate import YouTubeDownloaderApp


class TestUIDispatcher(unittest.TestCase):
    """Priority 4.2: Comprehensive test suite for thread-safe UI dispatcher using queue.Queue."""

    def setUp(self):
        self.mock_root = MagicMock()
        self.mock_root.after.return_value = "timer_12345"
        self.mock_root.winfo_exists.return_value = True

        self.app = YouTubeDownloaderApp.__new__(YouTubeDownloaderApp)
        self.app.root = self.mock_root
        self.app.app_dir = repo_root
        self.app.output_folder = repo_root
        self.app.formats = []
        self.app.video_formats = []
        self.app.audio_formats = []
        self.app.current_video_info = None
        self.app.current_video_title = None
        self.app.current_thumbnail_url = None
        self.app._thumb_img = None
        self.app.is_closing = False
        self.app.is_fetching = False
        self.app.is_downloading = False
        self.app._state_lock = threading.Lock()
        self.app.cancel_requested = threading.Event()
        self.app._poll_timer_id = None
        self.app._ui_poll_interval_ms = 20
        self.app._ui_queue = queue.Queue()

    def tearDown(self):
        self.app.is_closing = True
        self.app._stop_ui_polling()

    # 1. Worker thread enqueues callback without calling Tkinter
    def test_01_worker_thread_enqueues_without_calling_tkinter(self):
        mock_cb = MagicMock()
        executed_on_worker = threading.Event()

        def worker():
            self.app.run_on_ui_thread(mock_cb, "hello", key="value")
            executed_on_worker.set()

        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=2.0)

        self.assertTrue(executed_on_worker.is_set())
        # Tkinter APIs must NOT have been called from the worker thread
        self.mock_root.after.assert_not_called()
        self.mock_root.update.assert_not_called()
        self.mock_root.update_idletasks.assert_not_called()
        mock_cb.assert_not_called()

        # The callback must be safely in the queue
        self.assertFalse(self.app._ui_queue.empty())
        item = self.app._ui_queue.get_nowait()
        self.assertIs(item[0], mock_cb)
        self.assertEqual(item[1], ("hello",))
        self.assertEqual(item[2], {"key": "value"})

    # 2. Main thread executes queued callbacks via polling
    def test_02_main_thread_executes_queued_callbacks_via_poll(self):
        executed = []

        def cb1(a):
            executed.append(f"cb1:{a}")

        def cb2(b, extra=None):
            executed.append(f"cb2:{b}:{extra}")

        self.app._ui_queue.put((cb1, (42,), {}))
        self.app._ui_queue.put((cb2, ("test",), {"extra": "ok"}))

        # Simulate main-thread queue poll
        self.app._poll_ui_queue()

        self.assertEqual(executed, ["cb1:42", "cb2:test:ok"])
        self.assertTrue(self.app._ui_queue.empty())
        # Should have rescheduled the next poll on root
        self.mock_root.after.assert_called_with(20, self.app._poll_ui_queue)

    # 3. Synchronous draining for testing / shutdown
    def test_03_drain_ui_queue_synchronously(self):
        results = []
        for i in range(5):
            self.app._ui_queue.put((lambda val=i: results.append(val), (), {}))

        self.app.drain_ui_queue()
        self.assertEqual(results, [0, 1, 2, 3, 4])
        self.assertTrue(self.app._ui_queue.empty())

    # 4. Multiple callbacks execute in FIFO order
    def test_04_multiple_callbacks_execute_fifo_order(self):
        execution_order = []

        def worker_enqueue():
            for idx in range(15):
                self.app.run_on_ui_thread(lambda i=idx: execution_order.append(i))

        t = threading.Thread(target=worker_enqueue)
        t.start()
        t.join(timeout=2.0)

        self.app._poll_ui_queue()
        self.assertEqual(execution_order, list(range(15)))

    # 5. Callback exceptions do not stop subsequent callbacks or break polling loop
    def test_05_callback_exceptions_do_not_stop_subsequent_callbacks(self):
        results = []

        def bad_cb_1():
            raise ValueError("Deliberate error 1")

        def good_cb_1():
            results.append("first_good")

        def bad_cb_2():
            raise RuntimeError("Deliberate error 2")

        def good_cb_2():
            results.append("second_good")

        self.app._ui_queue.put((bad_cb_1, (), {}))
        self.app._ui_queue.put((good_cb_1, (), {}))
        self.app._ui_queue.put((bad_cb_2, (), {}))
        self.app._ui_queue.put((good_cb_2, (), {}))

        # Polling should execute both good callbacks despite the exceptions in bad ones
        with self.assertLogs('YouTubeMate', level='ERROR') as cm:
            self.app._poll_ui_queue()

        self.assertEqual(results, ["first_good", "second_good"])
        self.assertTrue(any("Unhandled exception in UI callback" in msg for msg in cm.output))
        # Poll rescheduled successfully
        self.mock_root.after.assert_called_with(20, self.app._poll_ui_queue)

    # 6. Shutdown prevents further callback execution
    def test_06_shutdown_prevents_further_callback_execution(self):
        mock_cb = MagicMock()
        self.app.is_closing = True

        # From background thread: should be dropped
        def worker():
            self.app.run_on_ui_thread(mock_cb)

        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=2.0)

        self.assertTrue(self.app._ui_queue.empty())
        mock_cb.assert_not_called()

        # From main thread: should be dropped
        self.app.run_on_ui_thread(mock_cb)
        mock_cb.assert_not_called()

        # Pre-existing items in queue are not executed if is_closing is True
        self.app._ui_queue.put((mock_cb, (), {}))
        self.app._poll_ui_queue()
        mock_cb.assert_not_called()

        # Polling is NOT rescheduled during shutdown
        self.mock_root.after.assert_not_called()

    # 7. No duplicate polling loops
    def test_07_no_duplicate_polling_loops(self):
        # Initial start
        self.assertIsNone(self.app._poll_timer_id)
        self.app._start_ui_polling()
        self.assertEqual(self.app._poll_timer_id, "timer_12345")
        self.assertEqual(self.mock_root.after.call_count, 1)

        # Second call while timer is active must NOT schedule another timer
        self.app._start_ui_polling()
        self.assertEqual(self.mock_root.after.call_count, 1)

        # Stop polling cancels timer and resets handle
        self.app._stop_ui_polling()
        self.mock_root.after_cancel.assert_called_once_with("timer_12345")
        self.assertIsNone(self.app._poll_timer_id)

        # Start again schedules a fresh single timer
        self.app._start_ui_polling()
        self.assertEqual(self.mock_root.after.call_count, 2)

    # 8. Main-thread synchronous fast-path
    def test_08_main_thread_synchronous_fast_path(self):
        executed = []

        def on_main(arg):
            executed.append(arg)

        # When called on main thread, executed immediately and synchronously
        self.app.run_on_ui_thread(on_main, "direct")
        self.assertEqual(executed, ["direct"])
        self.assertTrue(self.app._ui_queue.empty())

    # 9. Destroy root cleans up queue and polling timer
    def test_09_destroy_root_cleanup(self):
        self.app._poll_timer_id = "timer_to_cancel"
        mock_cb = MagicMock()
        self.app._ui_queue.put((mock_cb, (), {}))

        self.app._destroy_root()
        self.assertTrue(self.app.is_closing)
        self.assertIsNone(self.app._poll_timer_id)
        self.mock_root.after_cancel.assert_called_once_with("timer_to_cancel")
        self.assertTrue(self.app._ui_queue.empty())
        mock_cb.assert_not_called()
        self.mock_root.destroy.assert_called_once()

    # 10. Worker thread isolation: _fetch does not access Tkinter variables
    @patch('yt_dlp.YoutubeDL')
    def test_10_fetch_worker_does_not_access_tkinter_variables(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'title': 'Test Video',
            'duration': 120,
            'view_count': 1000,
            'thumbnail': 'http://example.com/thumb.jpg',
            'formats': [
                {'format_id': '18', 'vcodec': 'avc1', 'height': 360, 'ext': 'mp4', 'filesize': 1000000}
            ],
        }

        # Setup mock Tkinter variables that raise if accessed from non-main threads
        main_thread = threading.main_thread()

        def safe_get_auth():
            if threading.current_thread() is not main_thread:
                raise RuntimeError("Worker thread accessed auth_browser_value directly!")
            return config.DEFAULT_AUTH_BROWSER_DISPLAY

        def safe_get_mode():
            if threading.current_thread() is not main_thread:
                raise RuntimeError("Worker thread accessed download_mode_value directly!")
            return "Video (MP4 / WebM)"

        mock_auth_var = MagicMock()
        mock_auth_var.get.side_effect = safe_get_auth
        self.app.auth_browser_value = mock_auth_var

        mock_mode_var = MagicMock()
        mock_mode_var.get.side_effect = safe_get_mode
        self.app.download_mode_value = mock_mode_var

        self.app.url_entry = MagicMock()
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        self.app.ensure_js_runtime = MagicMock(return_value=True)
        self.app.meta_title_label = MagicMock()
        self.app.meta_channel_label = MagicMock()
        self.app.meta_duration_label = MagicMock()
        self.app.meta_views_label = MagicMock()
        self.app.thumb_label = MagicMock()
        self.app.format_combo = MagicMock()
        self.app.fetch_btn = MagicMock()
        self.app.download_btn = MagicMock()
        self.app.cancel_btn = MagicMock()
        self.app.mode_combo = MagicMock()
        self.app.auth_browser_combo = MagicMock()
        self.app.status_label = MagicMock()
        self.app.progress_value = MagicMock()
        self.app.eta_value = MagicMock()
        self.app.speed_value = MagicMock()
        self.app.progress_text = MagicMock()
        self.app.warning_value = MagicMock()

        self.app.fetch_formats()
        worker = self.app.active_worker
        self.assertIsNotNone(worker)
        worker.join(timeout=3.0)

        # Worker must have finished cleanly without throwing RuntimeError
        self.assertFalse(worker.is_alive())
        # Drain queued UI callbacks to simulate main loop processing
        self.app.drain_ui_queue()
        self.assertEqual(self.app.current_video_title, "Test Video")

    # 11. Worker thread isolation: _download does not access Tkinter variables
    @patch('yt_dlp.YoutubeDL')
    @patch('utils.file_utils.check_folder_writable', return_value=(True, None))
    def test_11_download_worker_does_not_access_tkinter_variables(self, mock_writable, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        main_thread = threading.main_thread()

        def safe_get_auth():
            if threading.current_thread() is not main_thread:
                raise RuntimeError("Worker thread accessed auth_browser_value directly!")
            return config.DEFAULT_AUTH_BROWSER_DISPLAY

        mock_auth_var = MagicMock()
        mock_auth_var.get.side_effect = safe_get_auth
        self.app.auth_browser_value = mock_auth_var

        self.app.url_entry = MagicMock()
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        self.app.ensure_js_runtime = MagicMock(return_value=True)
        self.app.formats = [("720p (HD) - mp4", "22", False, {'ext': 'mp4', 'filesize': 5000000}, False, None)]
        self.app.format_combo = MagicMock()
        self.app.format_combo.current.return_value = 0
        self.app.current_video_title = "Test Video"
        self.app.output_folder = repo_root
        self.app.fetch_btn = MagicMock()
        self.app.download_btn = MagicMock()
        self.app.cancel_btn = MagicMock()
        self.app.mode_combo = MagicMock()
        self.app.auth_browser_combo = MagicMock()
        self.app.status_label = MagicMock()
        self.app.progress_value = MagicMock()
        self.app.eta_value = MagicMock()
        self.app.speed_value = MagicMock()
        self.app.progress_text = MagicMock()
        self.app.warning_value = MagicMock()
        self.app.show_info_message = MagicMock()

        self.app.download_video()
        worker = self.app.active_worker
        self.assertIsNotNone(worker)
        worker.join(timeout=3.0)

        self.assertFalse(worker.is_alive())
        # Drain queued UI callbacks
        self.app.drain_ui_queue()
        self.app.show_info_message.assert_called_with("Success", "Video downloaded successfully!")

    # 12. Multiple application instances have isolated queues
    def test_12_per_instance_queue_isolation(self):
        app1 = YouTubeDownloaderApp.__new__(YouTubeDownloaderApp)
        app2 = YouTubeDownloaderApp.__new__(YouTubeDownloaderApp)

        q1 = app1._ui_queue
        q2 = app2._ui_queue

        self.assertIsNot(q1, q2)
        q1.put(("app1_task", (), {}))
        self.assertFalse(q1.empty())
        self.assertTrue(q2.empty())


if __name__ == '__main__':
    unittest.main()
