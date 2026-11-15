@echo off
rem One-click start for CivicPulse on Windows 10/11. Needs Python 3.12+ (python.org, tick "Add to PATH").
cd /d "%~dp0"

where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version >nul 2>nul || (echo Python is not installed. Get it from https://www.python.org/downloads/ & pause & exit /b 1)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY% -m venv .venv || (pause & exit /b 1)
)
if not exist ".venv\installed.flag" (
  echo Installing packages, first run only, takes a few minutes...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || (pause & exit /b 1)
  echo ok> ".venv\installed.flag"
)

set NEWDB=0
if not exist "db.sqlite3" set NEWDB=1
".venv\Scripts\python.exe" manage.py migrate --noinput || (pause & exit /b 1)
if "%NEWDB%"=="1" ".venv\Scripts\python.exe" manage.py seed_demo

echo.
echo CivicPulse is running at http://localhost:8000/  (close this window to stop)
start "" http://localhost:8000/login/
".venv\Scripts\python.exe" manage.py runserver 8000
pause
