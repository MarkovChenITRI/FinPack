# FinPack Build Script (PowerShell)
# Usage: .\build.ps1

Write-Host "========================================"
Write-Host "  FinPack Build Script"
Write-Host "========================================"
Write-Host ""

# Check Python
try {
    python --version
} catch {
    Write-Host "[ERROR] Python not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[1/5] Cleaning old files..."
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "build_venv") { Remove-Item -Recurse -Force "build_venv" }

Write-Host ""
Write-Host "[2/5] Creating clean virtual environment..."
python -m venv build_venv

Write-Host ""
Write-Host "[3/5] Installing packages..."
& .\build_venv\Scripts\python.exe -m pip install --upgrade pip
& .\build_venv\Scripts\pip.exe install -r requirements.txt
& .\build_venv\Scripts\pip.exe install pyinstaller

Write-Host ""
Write-Host "[4/5] Building exe..."
& .\build_venv\Scripts\pyinstaller.exe finpack.spec --noconfirm

Write-Host ""
Write-Host "[5/5] Creating cache folder..."
if (-not (Test-Path "dist\FinPack\cache")) {
    New-Item -ItemType Directory -Path "dist\FinPack\cache" | Out-Null
}

Write-Host ""
Write-Host "========================================"
Write-Host "  Build Complete!"
Write-Host "========================================"
Write-Host ""
Write-Host "Output: dist\FinPack\"
Write-Host "Exe: dist\FinPack\FinPack.exe"
Write-Host ""
