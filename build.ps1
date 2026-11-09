# YouTubeMate Automated Windows Packaging Script
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  YouTubeMate Desktop Packaging Script    " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$ErrorActionPreference = "Stop"

# 1. Install / verify dependencies
Write-Host "[1/4] Checking dependencies..." -ForegroundColor Yellow
python -m pip install -r requirements.txt --quiet

# 2. Generate icon assets
Write-Host "[2/4] Generating branding icon assets..." -ForegroundColor Yellow
python scripts/generate_branding_assets.py

# 3. Build standalone Windows executable
Write-Host "[3/4] Building standalone executable with PyInstaller..." -ForegroundColor Yellow
python -m PyInstaller YoutubeMate.spec --clean --noconfirm

# 4. Verify output
$exePath = "dist\YouTubeMate.exe"
if (Test-Path $exePath) {
    $item = Get-Item $exePath
    $sizeMb = [math]::Round($item.Length / 1MB, 2)
    Write-Host "[4/4] Build succeeded!" -ForegroundColor Green
    Write-Host "Executable location: $exePath ($sizeMb MB)" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Build failed: $exePath not found!" -ForegroundColor Red
    exit 1
}
