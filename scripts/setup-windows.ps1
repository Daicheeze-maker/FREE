# One-time setup for ClipForge AI on Windows 10/11.
# Right-click -> "Run with PowerShell" (or: powershell -ExecutionPolicy Bypass -File scripts\setup-windows.ps1)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Need($name, $wingetId, $check) {
    if (-not (Get-Command $check -ErrorAction SilentlyContinue)) {
        Write-Host "$name was not found. Installing with winget..." -ForegroundColor Yellow
        winget install -e --id $wingetId --accept-source-agreements --accept-package-agreements
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
        if (-not (Get-Command $check -ErrorAction SilentlyContinue)) {
            throw "$name was installed but is not on PATH yet. Close this window, open a new one and run the script again."
        }
    }
    Write-Host "OK  $name" -ForegroundColor Green
}

Need "Python 3.12" "Python.Python.3.12" "py"
Need "Node.js LTS" "OpenJS.NodeJS.LTS" "npm"
Need "FFmpeg" "Gyan.FFmpeg" "ffmpeg"

Write-Host "`nCreating the Python environment (backend\.venv)..."
if (-not (Test-Path "backend\.venv\Scripts\python.exe")) { py -3.12 -m venv backend\.venv }
& backend\.venv\Scripts\python.exe -m pip install --upgrade pip
& backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
# opencv-python (pulled in by some packages) duplicates opencv-python-headless; keep only headless.
& backend\.venv\Scripts\python.exe -m pip uninstall -y opencv-python 2>$null

Write-Host "`nBuilding the interface..."
Push-Location frontend
npm ci
npm run build
Pop-Location

Write-Host "`nDone. Double-click 'Start ClipForge.bat' to open the studio." -ForegroundColor Green
Write-Host "The first screen lets you download the AI models (about 670 MB for the recommended set)."
