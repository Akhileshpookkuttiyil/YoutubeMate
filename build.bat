@echo off
REM YouTubeMate Windows Build Script
echo ==========================================
echo   YouTubeMate Desktop Packaging Script
echo ==========================================

echo [1/4] Checking dependencies...
python -m pip install -r requirements.txt --quiet
if %ERRORLEVEL% NEQ 0 (
    echo Error installing dependencies.
    exit /b %ERRORLEVEL%
)

echo [2/4] Generating branding icon assets...
python scripts/generate_branding_assets.py
if %ERRORLEVEL% NEQ 0 (
    echo Error generating icon assets.
    exit /b %ERRORLEVEL%
)

echo [3/4] Building executable with PyInstaller...
python -m PyInstaller YoutubeMate.spec --clean --noconfirm
if %ERRORLEVEL% NEQ 0 (
    echo PyInstaller build failed.
    exit /b %ERRORLEVEL%
)

echo [4/4] Build complete! Executable is at dist\YouTubeMate.exe
echo ==========================================
