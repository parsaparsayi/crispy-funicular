# Virtual Avatar — Aria Fazlollah

**Live demo:** https://parsaparsayi.github.io/crispy-funicular/

This project produces short speaking-avatar clips from a photo + audio.
It includes:
- A simple Python pipeline (`grok.py`) with a CLI menu
- A local web control panel (`app.py` + `templates/`, `static/`)
- A public demo page under `/docs` (for GitHub Pages)
- Example deliverables (four short MP4s in the v1 Release)

## How to run the local GUI
```bash
pip install -r requirements.txt
python app.py
# then open http://127.0.0.1:5000
