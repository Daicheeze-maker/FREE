@echo off
REM Create an administrator account (asks for email, name and password).
REM Easier: start the store, open the sign-in page and click "Set up the admin account".
cd /d "%~dp0"
title Create an admin account
echo.
echo  Create an admin account for the store
echo  -------------------------------------
if not exist ".venv\Scripts\activate.bat" (
  echo  The store isn't set up on this computer yet.
  echo  Double-click start.bat once, wait until the store opens, close it, then run this again.
  echo.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m flask --app wsgi init-db >nul 2>nul
python -m flask --app wsgi create-admin
echo.
if errorlevel 1 (echo  The admin was NOT created. Read the message above.) else (echo  Done. Start the store and sign in with that email and password.)
echo.
pause
