@echo off
REM Start Aurelune with Waitress on Windows.
REM To allow other devices:  set HOST=0.0.0.0  then run this script (and open the firewall port, see README).
setlocal
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
REM Install anything new in requirements.txt (quick when everything is already there)
python -m pip install -q --disable-pip-version-check --retries 1 --timeout 10 -r requirements.txt
python -m flask --app wsgi init-db >nul
REM Loads the demo products only if the catalog is empty (never deletes anything)
python -m flask --app wsgi seed
python -m flask --app wsgi upgrade-demo
python -m flask --app wsgi ensure-admin
python serve.py
endlocal
