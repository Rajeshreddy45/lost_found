@echo off
setlocal
cd /d "%~dp0"
echo ==================================================
echo  CampusFind AI - Group 9 Flask Application
echo ==================================================
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating Python 3.13 environment...
  py -3.13 -m venv .venv
  if errorlevel 1 (
    echo Could not find Python 3.13. Install it and try again.
    pause
    exit /b 1
  )
)
echo [2/3] Checking and installing dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Installation failed. Please copy the error from this window.
  pause
  exit /b 1
)
echo [3/3] Starting Flask on http://127.0.0.1:5000
".venv\Scripts\python.exe" run.py
if errorlevel 1 pause
endlocal
