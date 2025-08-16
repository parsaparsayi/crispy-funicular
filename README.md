# Virtual Avatar with Your Personality (AI)

Speaking avatar powered by **Groq** (persona Q&A), **ElevenLabs** (TTS), and **D-ID** (lipsync).  
This repo contains:
- A **live demo page** (GitHub Pages) with 4 showcase videos (EN/FA, Intro/Q&A)
- A **CLI** tool (`grok.py`) to generate MP3s and MP4s
- An optional **local GUI** (`app.py`) control panel to run everything with clicks

---

## Live Demo (videos only)
- **GitHub Pages:** https://parsaparsayi.github.io/crispy-funicular/

This site hosts the four final demo MP4s. It doesn’t require any keys and works in any browser.

---

## Run Locally (CLI & GUI)

### Prerequisites
- Windows/macOS/Linux
- Python **3.10+**
- **FFmpeg** in your PATH (for local still-image video fallback)
- Your own API keys:
  - **Groq** (chat)
  - **ElevenLabs** (TTS)
  - **D-ID** (animation)
- Optional: GitHub token if you want the CLI to upload new MP3s to a Release

### Quick Start
```bash
# 1) Clone and enter the repo
git clone https://github.com/parsaparsayi/crispy-funicular.git
cd crispy-funicular

# 2) Create a virtual environment
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3) Install deps
pip install -r requirements.txt

# 4) Prepare .env from the example
copy .env.example .env   # (on macOS/Linux: cp .env.example .env)
# Fill .env with your own keys and defaults
