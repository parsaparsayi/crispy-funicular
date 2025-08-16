# Virtual Avatar with Your Personality

Speaking avatar built with:
- **Groq** — persona Q&A (text generation)
- **ElevenLabs** — text-to-speech (MP3)
- **D-ID** — lipsync animation (MP4)
- **FFmpeg** — still-image fallback video when D-ID isn’t used

This repository includes:
- A **live demo page** (GitHub Pages) with four showcase videos (EN/FA, Intro/Q&A)
- A **CLI** tool (`grok.py`) to generate MP3s and MP4s
- A **local GUI** (`app.py`) that runs the pipeline with buttons

---

## Live Demo (videos only)

- GitHub Pages: **https://parsaparsayi.github.io/crispy-funicular/**

This page hosts the final MP4 demos and plays in any browser. No keys required.

---

## Run Locally (CLI & GUI)

### Prerequisites

- Windows / macOS / Linux
- Python **3.10+**
- **FFmpeg** in your PATH  
  (Windows: grab a static build and add `ffmpeg.exe` to PATH; macOS: `brew install ffmpeg`; Linux: `sudo apt install ffmpeg`, etc.)
- Your own API keys:
  - **Groq** (for persona Q&A)
  - **ElevenLabs** (for TTS)
  - **D-ID** (for lipsync)
- Optional: a GitHub personal access token if you want the CLI to upload `output.mp3` to a Release for public hosting

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

# 3) Install dependencies
pip install -r requirements.txt

# 4) Prepare .env from the example
# Windows:
copy .env.example .env
# macOS/Linux:
cp .env.example .env

# 5) Open .env in a text editor and fill in:
#    GROQ_API_KEY, ELEVENLABS_API_KEY, DID_AUTH (username:password for D-ID)
#    DEFAULT_IMAGE_URL (https), DEFAULT_AUDIO_URL (https .mp3) if you have them
#    OUTPUT_DIR (short path, e.g., C:\AvatarOut)
#    Optional GitHub release settings if using upload
