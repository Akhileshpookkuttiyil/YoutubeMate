<div align="center">

<img src="assets/icon.png" alt="YouTubeMate Logo" width="128" height="128" />

# YouTubeMate

**Modern, High-Performance YouTube Video & Audio Desktop Downloader for Windows**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6.svg)](https://microsoft.com/windows)
[![Tests Passing](https://img.shields.io/badge/tests-116%20passed-brightgreen.svg)]()

</div>

---

## 📖 Overview

**YouTubeMate** is a modern, standalone desktop application engineered in Python and Tkinter for high-speed, reliable YouTube media downloads. Designed with a clean Windows dark theme, modular separation of concerns, and robust error recovery, it offers a seamless native desktop experience.

Whether downloading complete 4K/1080p videos with merged audio, native untouched M4A audio streams, or extracting MP3s, YouTubeMate simplifies media archiving with clear visual progress, metadata preview cards, and thread-safe cancellation.

---

## ✨ Key Features

- **🎬 Multi-Format Video Downloads**:
  - Full adaptive video downloads (4K, 1440p, 1080p, 720p, 480p, 360p).
  - Progressive single-file downloads (no FFmpeg required for 720p/360p progressive streams).
  - High-definition video and audio merging via FFmpeg.
- **🎵 Dedicated Audio-Only Modes**:
  - **Native M4A**: Instant direct audio download at highest available bitrate without transcoding or external tools.
  - **MP3 Conversion**: Post-processed MP3 audio at up to 192 kbps using FFmpeg.
- **🖼️ Rich Video Metadata Preview**:
  - Fetches and displays video thumbnail preview asynchronously.
  - Formatted channel name, duration, and formatted view counts.
- **🎨 Refined Modern Dark UI**:
  - Windows desktop aesthetic with dark slate background, card elevation, and visual hierarchy.
  - Interactive tooltips, clear typography (Segoe UI), responsive resizing, and keyboard shortcut support (Enter to fetch).
  - Dedicated brand icon applied across window titlebar, taskbar, and native executable.
- **🛡️ Thread Safety & Non-Blocking Architecture**:
  - UI stays 100% responsive during format extraction and downloads via isolated background workers.
  - Thread-safe UI dispatcher queue preventing race conditions and deadlocks.
  - Safe, clean cancellation mechanism that deletes incomplete temporary files (`.part`, `.ytdl`).
- **⚡ Resilient Error Handling**:
  - Automatic exponential backoff retries for transient network drops.
  - YouTube HTTP 429 rate-limit backoff and jitter management.
  - Optional browser cookie authentication (Chrome, Edge, Firefox) for age-restricted or private content.
- **📦 Windows Native Packaging**:
  - Fully self-contained standalone `.exe` with zero Python runtime required on target machines.
  - Multi-resolution Windows application icon (16, 32, 48, 64, 128, 256 px).

---

## 🖼️ Application Interface & Branding

<div align="center">
  <img src="assets/icon.png" alt="YouTubeMate Application Icon" width="160" height="160" />
  <p><em>YouTubeMate Desktop Application Identity (incorporating download geometry, local storage tray, and subtle video play concept)</em></p>
</div>

The desktop interface is structured into focused cards:
1. **Header**: Custom YouTubeMate branding, version pill, and dynamic runtime status indicator.
2. **URL Input & Auth Card**: URL entry box with Enter-to-fetch, fetch button, and optional browser cookie selector.
3. **Metadata Preview Card**: Video thumbnail display, title, channel name, duration, and view count.
4. **Controls Card**: Download mode selector, resolution/format dropdown with bitrate badges, and customizable destination directory picker.
5. **Progress & Status Card**: Real-time progress bar, percentage readout, download speed, ETA timer, and contextual status messages.
6. **Actions**: Instant download button and safe cancellation control.

---

## 🚀 Installation & Getting Started

### Prerequisites

- **Windows 10 / 11**
- **Python 3.10+** (Python 3.12 or 3.14 recommended)
- **Node.js** or **Deno** (Recommended: required by yt-dlp to solve YouTube player challenges)
- **FFmpeg** (Optional for progressive/M4A; required for 1080p+ HD merging and MP3 transcoding)

### 1. Running from Source

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Akhileshpookkuttiyil/YoutubeMate.git
   cd YoutubeMate
   ```

2. **Create and activate a virtual environment (optional but recommended):**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the application:**
   ```bash
   python YoutubeMate.py
   ```

---

## 🛠️ Building the Standalone Windows Executable

You can compile YouTubeMate into a single, standalone Windows `.exe` that runs without requiring Python to be installed.

### One-Click Build Script

In PowerShell:
```powershell
.\build.ps1
```

Or from Windows Command Prompt:
```cmd
build.bat
```

### Manual PyInstaller Build

```bash
python -m pip install -r requirements.txt
python scripts/generate_branding_assets.py
python -m PyInstaller YoutubeMate.spec --clean
```

The output executable will be created at:
```
dist/YouTubeMate.exe
```

---

## ⚙️ FFmpeg Requirements & Installation

While YouTubeMate works out of the box for standard progressive formats (720p/360p MP4) and direct audio (M4A), **FFmpeg** is required to:
- Merge separate high-definition video and audio streams (1080p, 1440p, 4K).
- Transcode audio to MP3.

### Recommended FFmpeg Installation Methods:

1. **Via Windows Package Manager (Winget)** *(Easiest)*:
   ```powershell
   winget install Gyan.FFmpeg
   ```
2. **Via Scoop / Chocolatey**:
   ```powershell
   scoop install ffmpeg
   # or
   choco install ffmpeg
   ```
3. **Portable (Bundled with App)**:
   - Download the essentials build from [ffmpeg.org](https://ffmpeg.org/download.html).
   - Place `ffmpeg.exe` and `ffprobe.exe` inside a `tools/` folder next to `YouTubeMate.exe` (or `YoutubeMate.py`).

YouTubeMate automatically scans system `PATH`, local directories, and standard Windows program locations on startup.

---

## 🧪 Testing and Quality Assurance

YouTubeMate features a comprehensive automated test suite with **116 unit and integration tests** covering UI thread dispatching, format parsing, authentication errors, rate limiting, cancellation, metadata, and file operations.

Run the test suite:
```bash
python -m unittest discover tests
```

Run Git whitespace/style checks:
```bash
git diff --check
```

---

## 📂 Project Architecture

```
YoutubeMate/
│
├── YoutubeMate.py               # Main application facade, lifecycle & controller
├── config.py                    # Global theme constants, paths, and configuration
├── requirements.txt             # Project and packaging dependencies
├── YoutubeMate.spec             # PyInstaller packaging configuration
├── build.ps1                    # Automated PowerShell packaging script
├── build.bat                    # Automated CMD build script
│
├── assets/                      # Application branding assets
│   ├── icon.ico                 # Multi-resolution Windows ICO (16, 32, 48, 64, 128, 256 px)
│   ├── icon.png                 # High-resolution primary PNG (512x512)
│   └── icon_*.png               # Individual resolution PNG assets
│
├── core/                        # Core domain and business logic
│   ├── downloader.py            # Download orchestration, error classification, retries
│   ├── ffmpeg_manager.py        # Executable discovery, validation & dependency scan
│   ├── format_manager.py        # Format sorting, filtering, tiering & labeling
│   ├── metadata_manager.py      # Video duration, views & thumbnail processing
│   └── progress_tracker.py      # Monotonic progress tracking & ETA formatting
│
├── ui/                          # Presentation layer
│   ├── main_window.py           # Responsive ttk grid layout & dark styling
│   ├── components.py            # Reusable UI widgets (tooltips, etc.)
│   └── dialogs.py               # Native user-facing dialogs & guidance
│
├── utils/                       # Common utilities
│   ├── file_utils.py            # Sanitization, collision handling, folder opening
│   └── logging_config.py        # Real-time flushing file & console logger
│
├── scripts/                     # Developer tools & asset generation
│   └── generate_branding_assets.py
│
└── tests/                       # Automated test suite (116 tests)
    ├── test_priority0.py        # Core download workflows & FFmpeg guards
    ├── test_priority1.py        # Lifecycle, thread safety & cancellation
    ├── test_priority2.py        # Formats, audio-only & metadata extraction
    ├── test_priority3.py        # Utilities, format manager & dependency detection
    ├── test_auth_and_ratelimit.py # Rate limits, backoff & browser cookies
    └── test_ui_dispatcher.py    # Thread-safe UI queue & polling loop
```

---

## ❓ Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **"Runtime Required" warning** | YouTube player extraction challenges require a JS runtime. | Install [Node.js](https://nodejs.org) or [Deno](https://deno.com). |
| **"FFmpeg Required for HD Video"** | 1080p/4K streams are served separately by YouTube and must be merged. | Run `winget install Gyan.FFmpeg` or place `ffmpeg.exe` in `tools/`. |
| **"Sign in to confirm you're not a bot"** | YouTube detected automated traffic. | Under **Browser Auth**, select your signed-in browser (Chrome, Edge, or Firefox). |
| **"Unable to access browser cookies"** | Browser process has locked its cookie database. | Close all running instances of that browser and try again. |
| **Download is slow or stalls** | Network fluctuation or YouTube rate limiting. | YouTubeMate automatically retries with backoff. Click **Cancel** and retry if needed. |

---

## 📄 License

This project is licensed under the MIT License.
