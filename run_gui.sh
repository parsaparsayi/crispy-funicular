#!/usr/bin/env bash
set -euo pipefail

# cd to repo root (the directory containing this script)
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create venv if missing
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate

# Upgrade pip and install deps
python -m pip install --upgrade pip
pip install -r requirements.txt

# Run GUI
echo "Starting GUI at http://127.0.0.1:5000"
python app.py
