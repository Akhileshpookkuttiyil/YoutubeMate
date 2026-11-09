import re
import time


class DownloadProgressTracker:
    """Tracks download progress monotonically across progressive streams and dual-stage adaptive merges."""

    def __init__(self, requires_merge=False, on_progress=None, video_size=None, audio_size=None):
        self.requires_merge = requires_merge
        self.on_progress = on_progress
        self.video_size = video_size if (isinstance(video_size, (int, float)) and video_size > 0) else None
        self.audio_size = audio_size if (isinstance(audio_size, (int, float)) and audio_size > 0) else None

        # Calculate dynamic stage weights if sizes are available
        if self.requires_merge and self.video_size and self.audio_size:
            total = self.video_size + self.audio_size
            self.video_weight = (self.video_size / total) * 95.0
            self.audio_weight = (self.audio_size / total) * 95.0
        else:
            self.video_weight = 85.0
            self.audio_weight = 10.0

        self.last_update_time = 0.0
        self.current_stage = 1
        self.last_percent = 0.0
        self.seen_filenames = set()

    @staticmethod
    def parse_percent(percent_text):
        if not percent_text:
            return 0.0
        match = re.search(r'(\d+(?:\.\d+)?)', str(percent_text))
        return float(match.group(1)) if match else 0.0

    def hook(self, d):
        status = d.get('status')
        now = time.time()

        if status == 'downloading':
            fn = d.get('filename')
            if fn and fn not in self.seen_filenames:
                if self.seen_filenames and self.requires_merge:
                    self.current_stage = 2
                self.seen_filenames.add(fn)

            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)

            if total_bytes and total_bytes > 0:
                stream_percent = (downloaded / total_bytes) * 100.0
                size_known = True
            else:
                stream_percent = self.parse_percent(d.get('_percent_str'))
                size_known = bool(stream_percent > 0)

            if self.requires_merge:
                if self.current_stage == 1:
                    overall_percent = (stream_percent / 100.0) * self.video_weight
                    stage_text = "Downloading video (Stage 1/2)..."
                else:
                    overall_percent = self.video_weight + ((stream_percent / 100.0) * self.audio_weight)
                    stage_text = "Downloading audio (Stage 2/2)..."
            else:
                overall_percent = min(stream_percent, 99.0)
                stage_text = "Downloading..."

            if not size_known and downloaded > 0:
                mb = downloaded / (1024 * 1024)
                stage_text = f"Downloading ({mb:.1f} MB downloaded)..."

            # Strict monotonicity across all stages and retried fragments
            overall_percent = max(self.last_percent, min(overall_percent, 99.0))
            self.last_percent = overall_percent

            speed = d.get('_speed_str', '')
            eta = d.get('_eta_str', '')

            # Throttle to max 10 updates per second (100ms) unless near completion
            if (now - self.last_update_time >= 0.10) or overall_percent >= 95.0:
                self.last_update_time = now
                if self.on_progress:
                    self.on_progress(overall_percent, eta, speed, stage_text)

        elif status == 'finished':
            if self.requires_merge:
                if self.current_stage == 1:
                    self.current_stage = 2
                    self.last_percent = max(self.last_percent, self.video_weight)
                    if self.on_progress:
                        self.on_progress(self.video_weight, "Preparing audio...", "", "Video downloaded. Starting audio (Stage 2/2)...")
                else:
                    self.last_percent = max(self.last_percent, 95.0)
                    if self.on_progress:
                        self.on_progress(95.0, "Merging files...", "", "Download complete. Merging streams...")
            else:
                self.last_percent = 99.0
                if self.on_progress:
                    self.on_progress(99.0, "Finalizing...", "", "Finalizing file...")

    def postprocessor_hook(self, d):
        status = d.get('status')
        pp = d.get('postprocessor', '')
        if status == 'started':
            if 'FFmpegVideoConvertor' in pp or 'Merger' in pp or 'FFmpegExtractAudio' in pp:
                if self.on_progress:
                    self.on_progress(96.0, "Merging streams...", "", "Processing audio/video with FFmpeg...")
        elif status == 'finished':
            if self.on_progress:
                self.on_progress(99.0, "Finalizing...", "", "Finishing output file...")
