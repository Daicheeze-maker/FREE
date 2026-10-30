@echo off
REM Start Velora with Waitress on Windows.
REM To allow other devices:  set HOST=0.0.0.0  then run this script (and open the firewall port, see README).
setlocal
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
flask --app wsgi init-db >nul
REM Loads the demo products only if the catalog is empty (never deletes anything)
flask --app wsgi seed
python serve.py
endlocal
