import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import tempfile
import threading

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from YoutubeMate import YouTubeDownloaderApp, DownloadProgressTracker


class TestPriority2DownloadExperienceAndOutput(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
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
        self.mock_root = MagicMock()
        self.mock_root.winfo_reqwidth.return_value = 780
        self.mock_root.winfo_reqheight.return_value = 720
        self.mock_root.winfo_screenwidth.return_value = 1920
        self.mock_root.winfo_screenheight.return_value = 1080
        self.mock_root.winfo_exists.return_value = True

        self.app = YouTubeDownloaderApp.__new__(YouTubeDownloaderApp)
        self.app.root = self.mock_root
        self.app.app_dir = repo_root
        self.app.formats = []
        self.app.video_formats = []
        self.app.audio_formats = []
        self.app.current_video_info = None
        self.app.current_video_title = "Test Video"
        self.app.current_thumbnail_url = None
        self.app._thumb_img = None
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

        # Mock widgets
        self.app.url_entry = MagicMock()
        self.app.fetch_btn = MagicMock()
        self.app.download_btn = MagicMock()
        self.app.cancel_btn = MagicMock()
        self.app.open_folder_btn = MagicMock()
        self.app.format_combo = MagicMock()
        self.app.mode_combo = MagicMock()
        self.app.status_label = MagicMock()
        self.app.warning_value = MagicMock()
        self.app.progress_value = MagicMock()
        self.app.eta_value = MagicMock()
        self.app.speed_value = MagicMock()
        self.app.progress_text = MagicMock()
        self.app.download_mode_value = MagicMock()
        self.app.download_mode_value.get.return_value = "Video (MP4 / WebM)"
        self.app.thumb_label = MagicMock()
        self.app.meta_title_label = MagicMock()
        self.app.meta_channel_label = MagicMock()
        self.app.meta_details_label = MagicMock()

    # Scenario 1: Every available resolution category extraction & sorting
    def test_01_resolution_category_extraction(self):
        sample_info = {
            'formats': [
                {'format_id': '313', 'height': 2160, 'vcodec': 'vp9', 'acodec': 'none', 'ext': 'webm', 'filesize': 800000000},
                {'format_id': '271', 'height': 1440, 'vcodec': 'vp9', 'acodec': 'none', 'ext': 'webm', 'filesize': 400000000},
                {'format_id': '137', 'height': 1080, 'vcodec': 'avc1.640028', 'acodec': 'none', 'ext': 'mp4', 'filesize': 150000000},
                {'format_id': '136', 'height': 720, 'vcodec': 'avc1.4d401f', 'acodec': 'none', 'ext': 'mp4', 'filesize': 80000000},
                {'format_id': '22', 'height': 720, 'vcodec': 'avc1.64001f', 'acodec': 'mp4a.40.2', 'ext': 'mp4', 'filesize': 90000000},
                {'format_id': '135', 'height': 480, 'vcodec': 'avc1.4d401e', 'acodec': 'none', 'ext': 'mp4', 'filesize': 40000000},
                {'format_id': '18', 'height': 360, 'vcodec': 'avc1.42001e', 'acodec': 'mp4a.40.2', 'ext': 'mp4', 'filesize': 20000000},
                {'format_id': '133', 'height': 240, 'vcodec': 'avc1.4d4015', 'acodec': 'none', 'ext': 'mp4', 'filesize': 10000000},
                {'format_id': '160', 'height': 144, 'vcodec': 'avc1.4d400c', 'acodec': 'none', 'ext': 'mp4', 'filesize': 5000000},
                {'format_id': 'sb0', 'format_note': 'storyboard'}, # Must be excluded
            ]
        }
        candidates = self.app.get_format_candidates(sample_info)
        fids = [c[0]['format_id'] for c in candidates]

        # Verify all standard resolution tiers are present in descending order
        self.assertIn('313', fids) # 2160p (4K)
        self.assertIn('271', fids) # 1440p (2K)
        self.assertIn('137', fids) # 1080p
        self.assertIn('136', fids) # 720p adaptive
        self.assertIn('22', fids)  # 720p progressive
        self.assertIn('135', fids) # 480p
        self.assertIn('18', fids)  # 360p progressive
        self.assertIn('133', fids) # 240p
        self.assertIn('160', fids) # 144p
        self.assertNotIn('sb0', fids) # Storyboard excluded

        # Verify resolution descending order: 2160p should come before 1080p and 360p
        idx_4k = fids.index('313')
        idx_1080 = fids.index('137')
        idx_360 = fids.index('18')
        self.assertLess(idx_4k, idx_1080)
        self.assertLess(idx_1080, idx_360)

    # Scenario 2: Progressive format identification
    def test_02_progressive_formats_labeling(self):
        f = {'format_id': '18', 'height': 360, 'vcodec': 'avc1', 'acodec': 'mp4a', 'ext': 'mp4', 'filesize': 15 * 1024 * 1024}
        label = self.app.build_format_label(f, requires_merge=False)
        self.assertIn("360p", label)
        self.assertIn("Single file", label)
        self.assertIn("15.0 MB", label)

    # Scenario 3: Adaptive formats identification
    def test_03_adaptive_formats_labeling(self):
        f = {'format_id': '137', 'height': 1080, 'vcodec': 'avc1', 'acodec': 'none', 'ext': 'mp4', 'filesize': 110 * 1024 * 1024}
        label = self.app.build_format_label(f, requires_merge=True)
        self.assertIn("1080p (Full HD)", label)
        self.assertIn("Video only", label)
        self.assertIn("110.0 MB", label)

    # Scenario 4: Audio-only M4A selection (Direct download, no FFmpeg needed)
    def test_04_audio_only_m4a_candidates(self):
        info = {
            'formats': [
                {'format_id': '140', 'vcodec': 'none', 'acodec': 'mp4a.40.2', 'ext': 'm4a', 'abr': 128, 'filesize': 4 * 1024 * 1024},
                {'format_id': '251', 'vcodec': 'none', 'acodec': 'opus', 'ext': 'webm', 'abr': 160, 'filesize': 5 * 1024 * 1024},
            ]
        }
        audio_cands = self.app.get_audio_candidates(info)
        m4a_entries = [c for c in audio_cands if c[5] == 'm4a']
        self.assertTrue(len(m4a_entries) >= 1)
        best_m4a = m4a_entries[0]
        # Must be single file and not require merge
        self.assertFalse(best_m4a[2]) # requires_merge = False
        self.assertIn("M4A", best_m4a[0])
        self.assertIn("No FFmpeg", best_m4a[0])

    # Scenario 5: Audio-only MP3 configuration (FFmpeg postprocessor)
    def test_05_audio_only_mp3_configuration(self):
        self.app.formats = [("Best Audio - MP3 (192 kbps)", "bestaudio/best", False, {}, True, 'mp3')]
        self.app.format_combo.current.return_value = 0
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        with patch.object(self.app, 'ensure_ffmpeg_for_audio', return_value=True), \
             patch('yt_dlp.YoutubeDL') as mock_ydl_cls, \
             patch('threading.Thread') as mock_thread:
            # Running download with MP3 should proceed when FFmpeg is present
            self.app.download_video()
            mock_thread.assert_called_once()

    # Scenario 6: Missing FFmpeg blocks MP3 audio and adaptive video
    def test_06_missing_ffmpeg_guards(self):
        self.app.ffmpeg_path = None
        self.app.ffmpeg_location = None

        # 1. MP3 download attempt without FFmpeg
        self.app.formats = [("Best Audio - MP3 (192 kbps)", "bestaudio/best", False, {}, True, 'mp3')]
        self.app.format_combo.current.return_value = 0
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        with patch.object(self.app, 'show_error_message') as mock_err, \
             patch('threading.Thread') as mock_thread:
            self.app.download_video()
            mock_err.assert_called_once()
            mock_thread.assert_not_called()

        # 2. Adaptive video attempt without FFmpeg
        self.app.formats = [("137 - 1080p - mp4", "137", True, {}, False, None)]
        with patch.object(self.app, 'show_error_message') as mock_err, \
             patch('threading.Thread') as mock_thread:
            self.app.download_video()
            mock_err.assert_called_once()
            mock_thread.assert_not_called()

    # Scenario 7: Video metadata extraction
    def test_07_metadata_extraction_display(self):
        info = {
            'title': 'Test Song Title',
            'uploader': 'Test Artist',
            'duration': 215, # 3 mins 35 secs
            'view_count': 1250000,
            'thumbnail': 'https://example.com/thumb.jpg',
            'formats': []
        }
        with patch.object(self.app, '_load_thumbnail_async') as mock_thumb_load:
            self.app.display_metadata_preview(info)
            self.app.meta_title_label.config.assert_called_with(text='Test Song Title')
            mock_thumb_load.assert_called_with('https://example.com/thumb.jpg')

        self.assertEqual(self.app.format_duration(215), "03:35")
        self.assertEqual(self.app.format_duration(3665), "1:01:05")

    # Scenario 8: Missing thumbnail & metadata fallback
    def test_08_missing_thumbnail_and_metadata_fallback(self):
        info_none = {
            'title': None,
            'uploader': None,
            'duration': None,
            'view_count': None,
            'thumbnail': None,
            'formats': []
        }
        try:
            self.app.display_metadata_preview(info_none)
            self.app.clear_metadata_preview()
        except Exception as e:
            self.fail(f"Fallback crashed on missing metadata: {e}")

    # Scenario 9: Safe duplicate filename handling
    def test_09_safe_duplicate_filenames(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create video.mp4
            existing1 = os.path.join(tmp_dir, "My Video.mp4")
            with open(existing1, "w") as f:
                f.write("existing")

            # Unique filename for second file must be "My Video (1)"
            name2 = self.app.get_unique_filename(tmp_dir, "My Video", "mp4")
            self.assertEqual(name2, "My Video (1)")

            # Create video (1).mp4
            existing2 = os.path.join(tmp_dir, "My Video (1).mp4")
            with open(existing2, "w") as f:
                f.write("existing 2")

            # Third file must be "My Video (2)"
            name3 = self.app.get_unique_filename(tmp_dir, "My Video", "mp4")
            self.assertEqual(name3, "My Video (2)")

    # Scenario 10: Filename sanitization
    def test_10_filename_sanitization(self):
        # Disallowed Windows chars: < > : " / \ | ? *
        bad_name = 'Illegal/Title: "Best Video?" * <Must See> | 2026'
        cleaned = self.app.sanitize_filename(bad_name)
        for char in '<>:"/\\|?*':
            self.assertNotIn(char, cleaned)
        self.assertTrue(len(cleaned) > 5)

    # Scenario 11: Destination folder validation & opening
    def test_11_destination_folder_validation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.app.output_folder = tmp_dir
            with patch('os.startfile', create=True) as mock_startfile:
                self.app.open_output_folder()
                mock_startfile.assert_called_with(tmp_dir)

    # Scenario 12: Existing cancellation functionality preservation
    def test_12_cancellation_preservation(self):
        self.app.is_downloading = True
        self.app.cancel_requested.clear()
        self.app.cancel_download()
        self.assertTrue(self.app.cancel_requested.is_set())

    # Scenario 13: Existing progress reporting preservation
    def test_13_progress_reporting_preservation(self):
        updates = []
        tracker = DownloadProgressTracker(
            requires_merge=False,
            on_progress=lambda p, eta, spd, text: updates.append(p)
        )
        tracker.hook({'status': 'downloading', 'downloaded_bytes': 500, 'total_bytes': 1000})
        self.assertTrue(len(updates) > 0)
        self.assertAlmostEqual(updates[-1], 50.0, places=1)

    # Scenario 14: UI state transitions with mode & folder buttons
    def test_14_ui_state_transitions(self):
        self.app.formats = [("18 - 360p", "18", False)]
        self.app.format_combo.current.return_value = 0

        # Downloading state disables mode_combo and inputs, enables cancel
        self.app.set_ui_state("downloading")
        self.app.fetch_btn.config.assert_called_with(state="disabled")
        self.app.download_btn.config.assert_called_with(state="disabled")
        self.app.cancel_btn.config.assert_called_with(state="normal")
        self.app.mode_combo.config.assert_called_with(state="disabled")

        # Idle state restores inputs
        self.app.set_ui_state("idle")
        self.app.fetch_btn.config.assert_called_with(state="normal")
        self.app.cancel_btn.config.assert_called_with(state="disabled")
        self.app.mode_combo.config.assert_called_with(state="readonly")
        self.app.download_btn.config.assert_called_with(state="normal")


if __name__ == '__main__':
    unittest.main()
