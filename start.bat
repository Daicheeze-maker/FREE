@echo off
REM ===========================================================================
REM  Velora Market: DOUBLE-CLICK THIS FILE to start the store.
REM  First run: sets everything up automatically (1-2 minutes, needs internet).
REM  After that: starts in a few seconds and opens your browser.
REM  To stop the store, press Ctrl+C in this window (or just close it).
REM ===========================================================================
setlocal
cd /d "%~dp0"
title Velora Market

if not exist ".venv\Scripts\activate.bat" (
  echo.
  echo  First run: setting things up. This takes a minute or two...
  echo.
  call scripts\setup.bat
  if errorlevel 1 (
    echo.
    echo  Setup did not finish. Scroll up to read the error.
    echo  Common fix: install Python 3.11 or newer from python.org and tick "Add python.exe to PATH".
    pause
    exit /b 1
  )
)

call .venv\Scripts\activate.bat
python -m flask --app wsgi init-db >nul
python -m flask --app wsgi seed >nul

set OPEN_BROWSER=1
if "%PORT%"=="" set PORT=5000
echo.
echo  Velora Market is starting at  http://127.0.0.1:%PORT%
echo  Your browser will open by itself. Press Ctrl+C here to stop the store.
echo.
python serve.py

echo.
echo  The store has stopped.
pause
endlocal
