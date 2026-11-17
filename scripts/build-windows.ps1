# Builds the Windows installer (ClipForge AI_x.y.z_x64-setup.exe).
# Prerequisites: scripts\setup-windows.ps1 has run, plus Rust (winget install Rustlang.Rustup)
# and the Visual Studio C++ Build Tools ("Desktop development with C++").
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "1/3 Building the interface"
Push-Location frontend; npm run build; Pop-Location

Write-Host "2/3 Packaging the engine (PyInstaller)"
& backend\.venv\Scripts\python.exe -m pip install pyinstaller
Push-Location backend
& .venv\Scripts\pyinstaller.exe clipforge-engine.spec --distpath ..\backend-dist --workpath ..\backend-build --noconfirm
Pop-Location

Write-Host "3/3 Building the desktop installer (Tauri)"
npm install
npm run desktop:build

Write-Host "`nInstaller: src-tauri\target\release\bundle\nsis\" -ForegroundColor Green
Write-Host "FFmpeg is not bundled: users install it with 'winget install Gyan.FFmpeg' or set its folder in Settings."
