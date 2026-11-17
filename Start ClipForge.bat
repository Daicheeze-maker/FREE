@echo off
rem Starts ClipForge AI. Run scripts\setup-windows.ps1 once first.
rem Keep this window open while you use ClipForge; close it to quit.
title ClipForge AI engine
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  echo ClipForge is not set up yet. Run scripts\setup-windows.ps1 first.
  pause
  exit /b 1
)
echo Starting ClipForge AI... the browser opens when the engine is ready.
echo Keep this window open while you use ClipForge. Close it to quit.
rem Open the browser only once the engine answers (up to 2 minutes).
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 120;$i++){try{$c=New-Object Net.Sockets.TcpClient('127.0.0.1',8756);$c.Close();Start-Process 'http://127.0.0.1:8756';break}catch{Start-Sleep -Milliseconds 1000}}"
".venv\Scripts\python.exe" -m clipforge.main --port 8756
echo.
echo The ClipForge engine stopped. If there is an error above, copy it for troubleshooting.
pause
