import os
import sys
import shutil
import subprocess
import re
from utils.logging_config import logger
from config import get_base_dir


def find_executable(executable_name, app_dir=None):
    """Finds executable in bundled/project directories or system PATH."""
    if not app_dir:
        app_dir = get_base_dir()

    candidates = [
        os.path.join(app_dir, "tools", executable_name),
        os.path.join(app_dir, "tools", executable_name, "bin"),
    ]

    # In packaged mode (PyInstaller), also check the directory of the actual .exe
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        if exe_dir and exe_dir != app_dir:
            candidates.extend([
                os.path.join(exe_dir, executable_name),
                os.path.join(exe_dir, "tools", executable_name),
                os.path.join(exe_dir, "tools", executable_name, "bin"),
            ])

    system_candidate = shutil.which(executable_name)
    if system_candidate:
        candidates.append(system_candidate)

    if os.name == "nt":
        candidates.extend([
            f"{candidates[0]}.exe",
            f"{candidates[1]}.exe",
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), executable_name, f"{executable_name}.exe"),
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), executable_name, "bin", f"{executable_name}.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", executable_name, f"{executable_name}.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", executable_name, "bin", f"{executable_name}.exe"),
            f"C:\\{executable_name}\\bin\\{executable_name}.exe",
            f"C:\\{executable_name}\\{executable_name}.exe",
        ])

    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return os.path.abspath(candidate)

    return None


def validate_ffmpeg_executable(ffmpeg_path):
    """Verifies that the file at ffmpeg_path is a functioning FFmpeg binary."""
    if not ffmpeg_path or not os.path.isfile(ffmpeg_path):
        return None
    try:
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)

        result = subprocess.run(
            [ffmpeg_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
            check=False,
            startupinfo=startupinfo,
            creationflags=creationflags
        )
        if result.returncode == 0:
            match = re.search(r"ffmpeg version\s+([^\s,]+)", result.stdout, re.IGNORECASE)
            version = match.group(1) if match else "detected"
            return version
    except Exception as e:
        logger.debug("Failed validating FFmpeg at '%s': %s", ffmpeg_path, e)
    return None


def find_ffmpeg(app_dir=None):
    """Discovers and validates FFmpeg binary from project tools or system PATH."""
    path = find_executable("ffmpeg", app_dir=app_dir)
    if not path:
        return None, None
    version = validate_ffmpeg_executable(path)
    if version:
        return path, version
    return None, None


def detect_dependencies(app_dir=None):
    """Detects JS runtimes (Node.js/Deno) and FFmpeg dependencies."""
    node_path = find_executable("node", app_dir=app_dir)
    deno_path = find_executable("deno", app_dir=app_dir)
    ffmpeg_path, ffmpeg_version = find_ffmpeg(app_dir=app_dir)

    js_runtime_name = None
    js_runtime_path = None
    if node_path:
        js_runtime_name = "node"
        js_runtime_path = node_path
    elif deno_path:
        js_runtime_name = "deno"
        js_runtime_path = deno_path

    ffmpeg_location = os.path.dirname(ffmpeg_path) if ffmpeg_path else None

    return {
        "node_path": node_path,
        "js_runtime_name": js_runtime_name,
        "js_runtime_path": js_runtime_path,
        "ffmpeg_path": ffmpeg_path,
        "ffmpeg_location": ffmpeg_location,
        "ffmpeg_version": ffmpeg_version,
    }
