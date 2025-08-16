@echo off
setlocal

REM Change to the directory of this script
cd /d "%~dp0"

REM Create venv if it doesn't exist
if not exist ".venv" (
  echo Creating virtual environment...
  python -m venv .venv
)

REM Activate venv
call ".venv\Scripts\activate"

REM Upgrade pip and install deps
python -m pip install --upgrade pip
pip install -r requirements.txt

REM Run the GUI
echo Starting GUI at http://127.0.0.1:5000
python app.py
