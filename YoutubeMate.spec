# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification file for YouTubeMate Desktop Application.
Builds a standalone, native Windows windowed executable with custom application icon,
bundled assets, and all required modular components.
"""

import os
import sys

block_cipher = None

# Ensure base directory is absolute
base_dir = os.path.abspath(SPECPATH)

datas = [
    (os.path.join(base_dir, 'assets'), 'assets'),
]

hiddenimports = [
    'config',
    'core',
    'core.downloader',
    'core.ffmpeg_manager',
    'core.format_manager',
    'core.metadata_manager',
    'core.progress_tracker',
    'ui',
    'ui.main_window',
    'ui.components',
    'ui.dialogs',
    'utils',
    'utils.file_utils',
    'utils.logging_config',
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'yt_dlp',
    'yt_dlp.compat',
    'yt_dlp.extractor',
    'yt_dlp.downloader',
    'yt_dlp.postprocessor',
]

a = Analysis(
    ['YoutubeMate.py'],
    pathex=[base_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'numpy', 'IPython', 'notebook', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='YouTubeMate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(base_dir, 'assets', 'icon.ico'),
)
