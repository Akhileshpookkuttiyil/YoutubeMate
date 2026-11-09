import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure repository root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from YoutubeMate import YouTubeDownloaderApp


class TestPriority0Scenarios(unittest.TestCase):

    def setUp(self):
        # Create a headless mock of Tk
        self.mock_root = MagicMock()
        self.mock_root.winfo_reqwidth.return_value = 780
        self.mock_root.winfo_reqheight.return_value = 640
        self.mock_root.winfo_screenwidth.return_value = 1920
        self.mock_root.winfo_screenheight.return_value = 1080

        # Instantiate app headless by avoiding mainloop and Tk window creation
        self.app = YouTubeDownloaderApp.__new__(YouTubeDownloaderApp)
        self.app.root = self.mock_root
        self.app.app_dir = repo_root
        self.app.formats = []
        self.app.output_folder = repo_root
        self.app.node_path = "C:\\fake\\node.exe"
        self.app.js_runtime_name = "node"
        self.app.js_runtime_path = "C:\\fake\\node.exe"
        self.app.ffmpeg_path = None
        self.app.ffmpeg_location = None
        self.app.ffmpeg_version = None
        self.app.format_placeholder = "Fetch formats to choose a quality"

        # Mock UI elements
        self.app.url_entry = MagicMock()
        self.app.fetch_btn = MagicMock()
        self.app.download_btn = MagicMock()
        self.app.format_combo = MagicMock()
        self.app.status_label = MagicMock()
        self.app.warning_value = MagicMock()
        self.app.progress_value = MagicMock()
        self.app.eta_value = MagicMock()
        self.app.speed_value = MagicMock()
        self.app.progress_text = MagicMock()

    # Scenario 1: Invalid YouTube URL (empty string triggers warning)
    def test_scenario_1_invalid_youtube_url(self):
        self.app.url_entry.get.return_value = "   "
        with patch.object(self.app, 'show_warning_message') as mock_warn:
            self.app.fetch_formats()
            mock_warn.assert_called_once_with("Input Required", "Please enter a YouTube URL.")

    # Scenario 2: Valid URL with no available formats
    def test_scenario_2_no_available_formats(self):
        empty_info = {'formats': []}
        candidates = self.app.get_format_candidates(empty_info)
        self.assertEqual(candidates, [])

        with patch.object(self.app, 'set_status') as mock_status, \
             patch.object(self.app, 'set_format_placeholder') as mock_placeholder:
            # Simulate what happens when formats are empty in fetch
            self.app.formats.clear()
            self.app.update_format_combo((), select_first=False)
            self.app.set_format_placeholder("No formats available")
            mock_placeholder.assert_called_with("No formats available")

    # Scenario 3: Format with height=None and missing metadata
    def test_scenario_3_format_with_height_none(self):
        info_with_none = {
            'formats': [
                {
                    'format_id': 'sb0',
                    'vcodec': 'none',
                    'acodec': 'none',
                    'format_note': 'storyboard',
                },
                {
                    'format_id': '137',
                    'vcodec': 'avc1.640028',
                    'acodec': 'none',
                    'height': None,
                    'fps': None,
                    'tbr': None,
                    'filesize': None,
                    'ext': 'mp4',
                },
                {
                    'format_id': '248',
                    'vcodec': 'vp9',
                    'acodec': 'none',
                    'height': 1080,
                    'fps': 30,
                    'tbr': 2000,
                    'filesize': 1048576,
                    'ext': 'webm',
                },
                {
                    'format_id': '18',
                    'vcodec': 'avc1.42001E',
                    'acodec': 'mp4a.40.2',
                    'height': 360,
                    'fps': None,
                    'tbr': None,
                    'ext': 'mp4',
                },
                {
                    'format_id': '140',
                    'vcodec': 'none',
                    'acodec': 'mp4a.40.2',
                    'height': None,
                },
            ]
        }
        # This must execute without raising TypeError
        candidates = self.app.get_format_candidates(info_with_none)
        self.assertTrue(len(candidates) >= 2)
        format_ids = [c[0]['format_id'] for c in candidates]
        self.assertIn('248', format_ids)
        self.assertIn('18', format_ids)
        self.assertNotIn('sb0', format_ids)
        self.assertNotIn('140', format_ids)

        # Verify build_format_label handles height=None
        format_info_none = {'format_id': 'test', 'height': None, 'ext': 'mp4'}
        label = self.app.build_format_label(format_info_none, requires_merge=False)
        self.assertIn("?p", label)
        self.assertIn("Single file", label)

    # Scenario 4: Progressive MP4 download (requires_merge=False)
    def test_scenario_4_progressive_download_configuration(self):
        self.app.formats = [("18 - 360p - mp4 - Single file", "18", False)]
        self.app.format_combo.current.return_value = 0
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        # Even if FFmpeg is missing, progressive download should NOT call ensure_ffmpeg
        self.app.ffmpeg_path = None
        self.app.ffmpeg_location = None

        with patch.object(self.app, 'ensure_ffmpeg') as mock_ffmpeg, \
             patch('threading.Thread') as mock_thread:
            self.app.download_video()
            # ensure_ffmpeg must NOT be called for progressive format
            mock_ffmpeg.assert_not_called()
            mock_thread.assert_called_once()

    # Scenario 5: Adaptive video/audio download (requires_merge=True)
    def test_scenario_5_adaptive_download_configuration(self):
        self.app.formats = [("137 - 1080p - mp4 - Video only", "137", True)]
        self.app.format_combo.current.return_value = 0
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        self.app.ffmpeg_path = "C:\\fake\\ffmpeg.exe"
        self.app.ffmpeg_location = "C:\\fake"

        ydl_opts = self.app.build_ydl_opts()
        selected_format_id = "137"
        selected_format_requires_merge = True

        format_spec = f"{selected_format_id}+bestaudio[ext=m4a]/bestaudio" if selected_format_requires_merge else selected_format_id
        ydl_opts.update({
            'format': format_spec,
            'outtmpl': os.path.join(self.app.output_folder, '%(title)s.%(ext)s'),
        })
        if selected_format_requires_merge:
            ydl_opts['merge_output_format'] = 'mp4'

        self.assertEqual(ydl_opts['format'], "137+bestaudio[ext=m4a]/bestaudio")
        self.assertEqual(ydl_opts['merge_output_format'], "mp4")
        self.assertNotIn('postprocessors', ydl_opts)
        self.assertEqual(ydl_opts['ffmpeg_location'], "C:\\fake")

    # Scenario 6: Missing FFmpeg aborts adaptive download cleanly
    def test_scenario_6_missing_ffmpeg_aborts_adaptive(self):
        self.app.formats = [("137 - 1080p - mp4 - Video only - needs FFmpeg", "137", True)]
        self.app.format_combo.current.return_value = 0
        self.app.url_entry.get.return_value = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        self.app.ffmpeg_path = None
        self.app.ffmpeg_location = None

        with patch.object(self.app, 'show_error_message') as mock_err, \
             patch('threading.Thread') as mock_thread:
            self.app.download_video()
            # Error dialog must be displayed and thread must NOT be launched
            mock_err.assert_called_once()
            self.assertEqual(mock_err.call_args[0][0], "FFmpeg Required")
            mock_thread.assert_not_called()

    # Scenario 7: Invalid FFmpeg path rejected by validate_ffmpeg
    @patch('subprocess.run')
    @patch('os.path.isfile')
    def test_scenario_7_invalid_ffmpeg_path(self, mock_isfile, mock_run):
        mock_isfile.return_value = True
        mock_proc = MagicMock()
        mock_proc.returncode = 1  # Fails execution
        mock_run.return_value = mock_proc

        valid, ver = self.app.validate_ffmpeg("C:\\corrupt\\ffmpeg.exe")
        self.assertFalse(valid)
        self.assertIsNone(ver)

    # Scenario 8: Successful FFmpeg detection and version parsing
    @patch('subprocess.run')
    @patch('os.path.isfile')
    def test_scenario_8_successful_ffmpeg_detection(self, mock_isfile, mock_run):
        mock_isfile.return_value = True
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "ffmpeg version 7.1-full_build Copyright (c) 2000-2024 FFmpeg developers\n"
        mock_run.return_value = mock_proc

        valid, ver = self.app.validate_ffmpeg("C:\\valid\\ffmpeg.exe")
        self.assertTrue(valid)
        self.assertEqual(ver, "7.1-full_build")

        # Test startup status formatting
        self.app.ffmpeg_location = "C:\\valid"
        self.app.ffmpeg_version = "7.1-full_build"
        status = self.app.get_startup_status()
        self.assertIn("FFmpeg detected (v7.1-full_build)", status)

    # Scenario 9: Extraction failure handled gracefully
    def test_scenario_9_extraction_failure_handling(self):
        with patch.object(self.app, 'show_error_message') as mock_err, \
             patch.object(self.app, 'set_status') as mock_status, \
             patch.object(self.app, 'set_controls_state') as mock_controls:
            # Simulate exception handling block of fetch_formats
            test_exc = Exception("Network unreachable")
            self.app.set_status("Failed to fetch formats.")
            self.app.reset_progress()
            self.app.update_format_combo((), select_first=False)
            self.app.set_format_placeholder("Fetch formats to try again")
            self.app.show_error_message("Error", str(test_exc))
            self.app.set_controls_state(True)

            mock_err.assert_called_with("Error", "Network unreachable")
            mock_status.assert_called_with("Failed to fetch formats.")
            mock_controls.assert_called_with(True)

    # Scenario 10: Download failure handled gracefully
    def test_scenario_10_download_failure_handling(self):
        with patch.object(self.app, 'show_error_message') as mock_err, \
             patch.object(self.app, 'set_status') as mock_status, \
             patch.object(self.app, 'set_controls_state') as mock_controls:
            # Simulate exception handling block of download_video
            test_exc = Exception("HTTP Error 403: Forbidden")
            self.app.set_status("Download failed.")
            self.app.reset_progress()
            self.app.show_error_message("Error", str(test_exc))
            self.app.set_controls_state(True)

            mock_err.assert_called_with("Error", "HTTP Error 403: Forbidden")
            mock_status.assert_called_with("Download failed.")
            mock_controls.assert_called_with(True)


if __name__ == '__main__':
    unittest.main()
