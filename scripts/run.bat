@echo off
REM Start Aurelune with Waitress on Windows.
REM To allow other devices:  set HOST=0.0.0.0  then run this script (and open the firewall port, see README).
setlocal
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
python -m flask --app wsgi init-db >nul
REM Loads the demo products only if the catalog is empty (never deletes anything)
python -m flask --app wsgi seed
python -m flask --app wsgi upgrade-demo
python serve.py
endlocal
