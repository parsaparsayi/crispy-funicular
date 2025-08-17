#!/usr/bin/env bash
set -euo pipefail

# Change to this script’s directory (repo root)
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Pick a Python executable
if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
else
  PYTHON=python
fi

# Create venv if missing
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  "$PYTHON" -m venv .venv
fi

# Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# Background helper: wait for port 5000, then open the default browser
python - <<'PY' &
import socket, time, webbrowser
HOST, PORT = "127.0.0.1", 5000
for _ in range(120):  # up to ~60 seconds
    try:
        with socket.create_connection((HOST, PORT), timeout=0.25):
            webbrowser.open(f"http://{HOST}:{PORT}/")
            break
    except OSError:
        time.sleep(0.5)
PY

echo "Starting GUI at http://127.0.0.1:5000"
python app.py

