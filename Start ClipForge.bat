@echo off
rem Starts ClipForge AI in your browser. Run scripts\setup-windows.ps1 once first.
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  echo ClipForge is not set up yet. Right-click scripts\setup-windows.ps1 and choose "Run with PowerShell".
  pause
  exit /b 1
)
start "" "http://127.0.0.1:8756"
".venv\Scripts\python.exe" -m clipforge.main --port 8756
if errorlevel 1 pause
