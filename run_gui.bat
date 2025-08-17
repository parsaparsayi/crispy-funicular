@echo off
setlocal

rem Change to this script’s directory (repo root)
cd /d "%~dp0"

rem Create venv if missing
if not exist ".venv" (
  echo Creating virtual environment...
  python -m venv .venv
)

rem Activate venv
call ".venv\Scripts\activate"

rem Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

rem Launch a helper that waits for port 5000 to be reachable, then opens the browser.
rem Runs in parallel so app.py can start normally.
start "" powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "for($i=0;$i -lt 60;$i++){try{$c=New-Object Net.Sockets.TcpClient('127.0.0.1',5000);$c.Close(); Start-Process 'http://127.0.0.1:5000/'; break}catch{}; Start-Sleep -Milliseconds 500}"

rem Start the Flask app (blocks until you press Ctrl+C)
echo Starting GUI at http://127.0.0.1:5000
python app.py

