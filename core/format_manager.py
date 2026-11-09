from config import STANDARD_RESOLUTIONS


def safe_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def format_filesize(bytes_val):
    """Formats numeric bytes into human-readable size string."""
    b = safe_int(bytes_val)
    if b <= 0:
        return ""
    if b < 1024:
        return f"{b} B"
    kb = b / 1024.0
    if kb < 1024:
        return f"{kb:.1f} KB"
    mb = kb / 1024.0
    if mb < 1024:
        return f"{mb:.1f} MB"
    gb = mb / 1024.0
    return f"{gb:.2f} GB"


def is_valid_format(f):
    if not isinstance(f, dict):
        return False
    if not f.get('format_id'):
        return False
    if f.get('ext') in {'mhtml', 'jpg', 'jpeg', 'png', 'webp'}:
        return False
    if f.get('format_note') == 'storyboard':
        return False
    vcodec = f.get('vcodec')
    if not vcodec or vcodec == 'none':
        return False
    height = safe_int(f.get('height'))
    if height <= 0:
        return False
    return True


def is_valid_audio_format(f):
    if not isinstance(f, dict):
        return False
    if not f.get('format_id'):
        return False
    if f.get('ext') in {'mhtml', 'jpg', 'jpeg', 'png', 'webp'}:
        return False
    if f.get('format_note') == 'storyboard':
        return False
    vcodec = f.get('vcodec')
    if vcodec and vcodec != 'none':
        return False
    acodec = f.get('acodec')
    if not acodec or acodec == 'none':
        return False
    return True


def format_sort_key(f):
    height = safe_int(f.get('height'))
    fps = safe_float(f.get('fps'))
    tbr = safe_float(f.get('tbr'))
    filesize = safe_int(f.get('filesize') or f.get('filesize_approx'))
    is_mp4 = 1 if f.get('ext') == 'mp4' else 0
    return (height, fps, is_mp4, tbr, filesize)


def format_resolution_label(height):
    h = safe_int(height)
    if h >= 2160:
        return "2160p (4K)"
    if h >= 1440:
        return "1440p (2K)"
    if h >= 1080:
        return "1080p (Full HD)"
    if h >= 720:
        return "720p (HD)"
    if h >= 480:
        return "480p (SD)"
    if h >= 360:
        return "360p"
    if h >= 240:
        return "240p"
    if h >= 144:
        return "144p"
    return f"{h}p" if h > 0 else "?p"


def get_format_candidates(info):
    """Filters, deduplicates, and categorizes video formats into standard resolution tiers."""
    if not info or not isinstance(info, dict):
        return []

    raw_formats = info.get('formats') or []
    valid_formats = [f for f in raw_formats if is_valid_format(f)]
    if not valid_formats:
        return []

    progressive = [f for f in valid_formats if f.get('acodec') and f.get('acodec') != 'none']
    adaptive = [f for f in valid_formats if not f.get('acodec') or f.get('acodec') == 'none']

    by_tier_prog = {}
    for f in sorted(progressive, key=format_sort_key, reverse=True):
        h = safe_int(f.get('height'))
        for tier in STANDARD_RESOLUTIONS:
            if h >= tier - 20 and h <= tier + 20:
                if tier not in by_tier_prog:
                    by_tier_prog[tier] = f
                break

    by_tier_adapt = {}
    for f in sorted(adaptive, key=format_sort_key, reverse=True):
        h = safe_int(f.get('height'))
        for tier in STANDARD_RESOLUTIONS:
            if h >= tier - 20 and h <= tier + 20:
                if tier not in by_tier_adapt:
                    by_tier_adapt[tier] = f
                break

    candidates = []
    seen_format_ids = set()

    for tier in STANDARD_RESOLUTIONS:
        f_prog = by_tier_prog.get(tier)
        f_adapt = by_tier_adapt.get(tier)

        if f_prog:
            fid = f_prog.get('format_id')
            if fid and fid not in seen_format_ids:
                candidates.append((f_prog, False))
                seen_format_ids.add(fid)

        if f_adapt:
            fid = f_adapt.get('format_id')
            if fid and fid not in seen_format_ids:
                candidates.append((f_adapt, True))
                seen_format_ids.add(fid)

    if not candidates:
        for f in sorted(progressive, key=format_sort_key, reverse=True):
            fid = f.get('format_id')
            if fid and fid not in seen_format_ids:
                candidates.append((f, False))
                seen_format_ids.add(fid)

    if not candidates:
        for f in sorted(valid_formats, key=format_sort_key, reverse=True):
            fid = f.get('format_id')
            if fid and fid not in seen_format_ids:
                req_merge = not bool(f.get('acodec') and f.get('acodec') != 'none')
                candidates.append((f, req_merge))
                seen_format_ids.add(fid)

    return candidates


def get_audio_candidates(info, ffmpeg_location=None):
    """Categorizes audio formats into direct M4A stream, MP3 conversion, and raw audio streams."""
    if not info or not isinstance(info, dict):
        return []

    raw_formats = info.get('formats') or []
    valid_audio = [f for f in raw_formats if is_valid_audio_format(f)]
    valid_audio = sorted(
        valid_audio,
        key=lambda f: (safe_float(f.get('abr') or f.get('tbr')), safe_int(f.get('filesize'))),
        reverse=True,
    )

    candidates = []
    best_m4a = next((f for f in valid_audio if f.get('ext') == 'm4a'), None)
    if best_m4a:
        fid = best_m4a.get('format_id')
        size = best_m4a.get('filesize') or best_m4a.get('filesize_approx')
        size_str = f" (~{format_filesize(size)})" if size else ""
        abr = safe_int(best_m4a.get('abr'))
        abr_str = f" ({abr} kbps)" if abr > 0 else ""
        label = f"Best Audio - M4A{abr_str}{size_str} - [Single file - No FFmpeg] ({fid})"
        candidates.append((label, fid, False, best_m4a, True, 'm4a'))
    else:
        label = "Best Audio - M4A - [Single file - No FFmpeg] (bestaudio)"
        candidates.append((label, "bestaudio[ext=m4a]/bestaudio/best", False, {}, True, 'm4a'))

    ffmpeg_note = "[Video only - FFmpeg merge]" if ffmpeg_location else "[Video only - needs FFmpeg]"
    label_mp3 = f"Best Audio - MP3 (192 kbps) - {ffmpeg_note}"
    candidates.append((label_mp3, "bestaudio/best", False, {}, True, 'mp3'))

    seen_fids = set()
    for f in valid_audio:
        fid = f.get('format_id')
        if not fid or fid in seen_fids:
            continue
        seen_fids.add(fid)
        ext = f.get('ext') or 'audio'
        abr = safe_int(f.get('abr') or f.get('tbr'))
        abr_str = f"{abr} kbps - " if abr > 0 else ""
        size = f.get('filesize') or f.get('filesize_approx')
        size_str = f" (~{format_filesize(size)})" if size else ""
        label = f"{abr_str}{ext}{size_str} - [Single file] ({fid})"
        candidates.append((label, fid, False, f, True, ext))

    return candidates


def build_format_label(format_info, requires_merge, ffmpeg_location=None):
    """Builds a human-readable format label for GUI dropdown."""
    height = format_info.get('height')
    res_str = format_resolution_label(height)
    ext = format_info.get('ext') or 'unknown'
    fid = format_info.get('format_id', 'unknown')

    filesize = format_info.get('filesize') or format_info.get('filesize_approx')
    size_str = f" (~{format_filesize(filesize)})" if filesize else ""

    if requires_merge:
        note = "Video only - needs FFmpeg" if not ffmpeg_location else "Video only"
    else:
        note = "Single file"

    return f"{fid} - {res_str} - {ext}{size_str} - {note}"
