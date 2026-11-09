from tkinter import messagebox


def show_error(title, message):
    messagebox.showerror(title, message)


def show_warning(title, message):
    messagebox.showwarning(title, message)


def show_info(title, message):
    messagebox.showinfo(title, message)


def get_ffmpeg_guidance_text(is_audio=False, codec='mp3'):
    if is_audio:
        title = "FFmpeg Required for MP3"
        msg = (
            "Converting audio to MP3 requires FFmpeg.\n\n"
            "Quick Alternative: Switch Download Mode to 'Audio Only (M4A)' to download "
            "the high-quality native audio stream immediately with zero conversion and no FFmpeg required.\n\n"
            "To enable MP3 conversion:\n"
            "1. Download FFmpeg from https://ffmpeg.org\n"
            "2. Place ffmpeg.exe in a 'tools' folder next to YouTubeMate or add it to your system PATH."
        )
    else:
        title = "FFmpeg Required for HD Video"
        msg = (
            "High quality video formats (1080p, 4K) are served by YouTube as separate "
            "video-only streams and require FFmpeg to merge with audio.\n\n"
            "To enable HD merging:\n"
            "1. Download FFmpeg from https://ffmpeg.org\n"
            "2. Place ffmpeg.exe in a 'tools' folder next to YouTubeMate or add it to your system PATH.\n\n"
            "Alternatively, select a format marked '[Single file]' (such as 720p or 360p progressive)."
        )
    return title, msg
