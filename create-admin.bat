@echo off
REM Create an administrator account (asks for email, name and password).
cd /d "%~dp0.."
if not exist ".venv\Scripts\activate.bat" (
  echo Run start.bat once first so everything gets installed.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m flask --app wsgi init-db >nul
python -m flask --app wsgi create-admin
pause
