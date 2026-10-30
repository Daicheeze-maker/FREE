@echo off
REM One-time setup on Windows 10/11: virtualenv, dependencies, .env, database + demo data.
setlocal
cd /d "%~dp0\.."

where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ required'" || exit /b 1

if not exist .venv (%PY% -m venv .venv)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt || exit /b 1

if not exist .env (
  copy .env.example .env >nul
  for /f %%k in ('python -c "import secrets; print(secrets.token_hex(32))"') do (
    python -c "import re,pathlib; p=pathlib.Path('.env'); p.write_text(re.sub(r'(?m)^SECRET_KEY=.*$', 'SECRET_KEY=%%k', p.read_text()))"
  )
  echo Created .env with a fresh SECRET_KEY.
)

flask --app wsgi init-db || exit /b 1
flask --app wsgi seed || exit /b 1
echo Setup complete. Start with: scripts\run.bat
endlocal
