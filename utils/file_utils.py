import os
import re
import sys
import subprocess
from utils.logging_config import logger


def sanitize_filename(name, max_length=200):
    """Sanitizes filename for cross-platform and Windows filesystem safety."""
    if not name or not isinstance(name, str):
        return "video"

    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    sanitized = sanitized.rstrip('. ')

    reserved = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    if sanitized.upper() in reserved or not sanitized:
        sanitized = f"_{sanitized}" if sanitized else "video"

    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip('. ')

    return sanitized or "video"


def get_unique_filename(folder, base_name, ext):
    """Generates unique non-colliding base filename in folder by appending (1), (2), etc."""
    sanitized_base = sanitize_filename(base_name)
    ext = ext.lstrip('.')
    candidate = f"{sanitized_base}.{ext}"

    if not os.path.exists(os.path.join(folder, candidate)):
        return sanitized_base

    counter = 1
    while True:
        candidate_base = f"{sanitized_base} ({counter})"
        candidate = f"{candidate_base}.{ext}"
        if not os.path.exists(os.path.join(folder, candidate)):
            return candidate_base
        counter += 1


def open_folder(folder_path):
    """Opens directory in default OS file explorer."""
    if not folder_path or not os.path.exists(folder_path):
        return False

    try:
        if sys.platform == 'win32':
            os.startfile(os.path.abspath(folder_path))
            return True
        elif sys.platform == 'darwin':
            subprocess.run(['open', os.path.abspath(folder_path)], check=True)
            return True
        else:
            subprocess.run(['xdg-open', os.path.abspath(folder_path)], check=True)
            return True
    except Exception as e:
        logger.error("Failed to open output directory '%s': %s", folder_path, e)
        return False


def check_folder_writable(folder_path):
    """Verifies that the target folder exists and has write permission."""
    if not folder_path or not os.path.isdir(folder_path):
        return False, "Destination directory does not exist."
    try:
        test_file = os.path.join(folder_path, f".test_write_perm_{os.getpid()}.tmp")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("test")
        os.remove(test_file)
        return True, ""
    except Exception as e:
        return False, f"Permission denied: Unable to write to destination folder ({e})."
