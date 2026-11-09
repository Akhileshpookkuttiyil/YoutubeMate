import os
import sys
import subprocess
import urllib.request
import tempfile
from utils.logging_config import logger


def format_duration(seconds):
    """Formats duration in seconds to MM:SS or HH:MM:SS."""
    if not seconds:
        return ""
    try:
        s = int(seconds)
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        if h > 0:
            return f"{h}:{m:02d}:{sec:02d}"
        return f"{m:02d}:{sec:02d}"
    except (ValueError, TypeError):
        return ""


def format_view_count(views):
    """Formats numeric view count into human-readable format (e.g. 1.2M views)."""
    if not views:
        return ""
    try:
        v = int(views)
        if v >= 1_000_000_000:
            return f"{v / 1_000_000_000:.1f}B views"
        if v >= 1_000_000:
            return f"{v / 1_000_000:.1f}M views"
        if v >= 1_000:
            return f"{v / 1_000:.1f}K views"
        return f"{v} views"
    except (ValueError, TypeError):
        return ""


def download_and_process_thumbnail(thumb_url, target_width=120, target_height=68):
    """Downloads thumbnail and processes it into either a PIL Image or temp PNG file path.

    Returns (pil_image, temp_png_path). Does not touch Tkinter (strictly thread-safe).
    """
    if not thumb_url:
        return None, None

    try:
        req = urllib.request.Request(thumb_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw_data = resp.read()

        # Try Pillow first
        try:
            import io
            from PIL import Image
            pil_img = Image.open(io.BytesIO(raw_data))
            pil_img = pil_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            return pil_img, None
        except Exception:
            pass

        # Windows PowerShell System.Drawing fallback
        if sys.platform == 'win32':
            try:
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f_in:
                    f_in.write(raw_data)
                    in_path = f_in.name
                out_path = in_path + '.png'
                ps_cmd = (
                    f"Add-Type -AssemblyName System.Drawing; "
                    f"$b = [System.Drawing.Bitmap]::new('{in_path}'); "
                    f"$r = [System.Drawing.Bitmap]::new($b, {target_width}, {target_height}); "
                    f"$r.Save('{out_path}', [System.Drawing.Imaging.ImageFormat]::Png); "
                    f"$b.Dispose(); $r.Dispose()"
                )
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)

                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    check=True,
                    startupinfo=startupinfo,
                    creationflags=creationflags,
                    timeout=4,
                )
                try:
                    os.remove(in_path)
                except Exception:
                    pass

                if os.path.exists(out_path):
                    return None, out_path
            except Exception as e:
                logger.debug("PowerShell thumbnail resize failed: %s", e)

    except Exception as e:
        logger.debug("Thumbnail download failed: %s", e)

    return None, None
