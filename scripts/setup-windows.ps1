# One-time setup for ClipForge AI on Windows 10/11.
# Right-click -> "Run with PowerShell" (or: powershell -ExecutionPolicy Bypass -File scripts\setup-windows.ps1)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$venvPy = Join-Path $root "backend\.venv\Scripts\python.exe"

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

# Native programs do not throw on failure in Windows PowerShell; check their exit code ourselves.
function Run($what) {
    if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE). See the messages above." }
}

function Has-Python312 {
    # Windows PowerShell 5.1 turns redirected stderr into a terminating error under "Stop"; relax it here.
    $ErrorActionPreference = "Continue"
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) { return $false }
    & py -3.12 -c "import sys" 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Need-Tool($name, $wingetId, $check) {
    if (-not (Get-Command $check -ErrorAction SilentlyContinue)) {
        Write-Host "$name was not found. Installing with winget..." -ForegroundColor Yellow
        winget install -e --id $wingetId --accept-source-agreements --accept-package-agreements
        Refresh-Path
        if (-not (Get-Command $check -ErrorAction SilentlyContinue)) {
            throw "$name was installed but is not on PATH yet. Close this window, open a new one and run the script again."
        }
    }
    Write-Host "OK  $name" -ForegroundColor Green
}

try {
    # Python 3.12 specifically: the py launcher alone is not enough.
    if (-not (Has-Python312)) {
        Write-Host "Python 3.12 was not found. Installing with winget..." -ForegroundColor Yellow
        winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
        Refresh-Path
        if (-not (Has-Python312)) {
            throw "Python 3.12 was installed but cannot be found yet. Close this window, open a new one and run the script again."
        }
    }
    Write-Host "OK  Python 3.12" -ForegroundColor Green
    Need-Tool "Node.js LTS" "OpenJS.NodeJS.LTS" "npm"
    Need-Tool "FFmpeg" "Gyan.FFmpeg" "ffmpeg"

    Write-Host "`nCreating the Python environment (backend\.venv)..."
    if (-not (Test-Path $venvPy)) {
        & py -3.12 -m venv (Join-Path $root "backend\.venv"); Run "Creating the Python environment"
    }
    & $venvPy -m pip install --upgrade pip; Run "Updating pip"
    & $venvPy -m pip install -r (Join-Path $root "backend\requirements.txt"); Run "Installing Python packages"
    # Note: never uninstall opencv-python here. It shares the cv2 folder with opencv-python-headless,
    # so removing one deletes the other's files too.
    Write-Host "Checking that the engine's packages load..."
    & $venvPy -c "import cv2, numpy, sherpa_onnx, scenedetect, fastapi, sqlalchemy, uvicorn"
    if ($LASTEXITCODE -ne 0) {
        & $venvPy -m pip install --force-reinstall --no-deps opencv-python-headless; Run "Repairing OpenCV"
        & $venvPy -c "import cv2, numpy, sherpa_onnx, scenedetect, fastapi, sqlalchemy, uvicorn"; Run "Checking the engine's packages"
    }

    Write-Host "`nBuilding the interface..."
    Push-Location (Join-Path $root "frontend")
    try {
        npm ci; Run "Installing interface packages (npm ci)"
        npm run build; Run "Building the interface"
    } finally { Pop-Location }

    & (Join-Path $PSScriptRoot "install-shortcut.ps1")
    Write-Host "`nDone. Double-click 'ClipForge AI' on your Desktop to open the studio." -ForegroundColor Green
    Write-Host "The first screen lets you download the AI models (about 670 MB for the recommended set)."
}
catch {
    Write-Host "`nSetup stopped: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Fix the problem above and run this script again. Steps that already finished are skipped."
    exit 1
}
