# grok.py
# Virtual avatar pipeline:
# - Persona chat via Groq (optional)
# - TTS via ElevenLabs (saves output.mp3 next to this file)
# - Animation via D-ID (or local FFmpeg still-image fallback)
# - Optional: upload output.mp3 to a GitHub release and reuse its public URL

import os
import time
import base64
import requests
import subprocess
import tempfile
import platform
import shutil
from datetime import datetime
from dotenv import load_dotenv

PIPELINE_VERSION = "avatar-pipeline r9 (startswith fix, local D-ID save, sturdier fallbacks)"
print(PIPELINE_VERSION)

# ------------------------------ Environment & Paths ------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

print("Running file:", os.path.abspath(__file__))
print("Working dir :", os.getcwd())

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH, override=True)
    print(f".env loaded from {ENV_PATH}")
else:
    print(f"No .env file found in {BASE_DIR}")

# Output dir (use a short path on Windows to avoid MAX_PATH issues)
OUTPUT_DIR = os.getenv("OUTPUT_DIR", tempfile.gettempdir())
os.makedirs(OUTPUT_DIR, exist_ok=True)

VOICE_ID_PATH     = os.path.join(BASE_DIR, "voice_id.txt")
OUTPUT_MP3        = os.path.join(BASE_DIR, "output.mp3")  # TTS target (local)
VOICE_SAMPLE_PATH = os.path.join(BASE_DIR, "voice cloning.mp3")  # sample for cloning

# Required keys
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
DID_AUTH           = os.getenv("DID_AUTH")  # plain "username:password" (script encodes it)

# Persona fields
USER_NAME      = os.getenv("USER_NAME", "Aria Fazlollah")
USER_BIRTHDATE = os.getenv("USER_BIRTHDATE", "1987-04-29")
USER_CITY      = os.getenv("USER_CITY", "Tehran, Iran")
USER_BIO       = os.getenv("USER_BIO", "I’m into AI and plan to master it in a few years.")

# GitHub release config (for public audio hosting)
GITHUB_TOKEN        = os.getenv("GITHUB_TOKEN")
GITHUB_REPO         = os.getenv("GITHUB_REPO")          # e.g. "owner/repo"
GITHUB_RELEASE_TAG  = os.getenv("GITHUB_RELEASE_TAG", "v1")
GITHUB_RELEASE_NAME = os.getenv("GITHUB_RELEASE_NAME", GITHUB_RELEASE_TAG)
GITHUB_ASSET_NAME   = os.getenv("GITHUB_ASSET_NAME", "output.mp3")

def _mask(k: str):
    if not k:
        return None
    return k[:10] + "..." if len(k) > 13 else "***"

print("GROQ_API_KEY:", _mask(GROQ_API_KEY))
print("ELEVENLABS_API_KEY:", _mask(ELEVENLABS_API_KEY))
print("DID_AUTH set:", bool(DID_AUTH))

# Defaults controlled by .env
def _env_default_audio():
    return os.getenv(
        "DEFAULT_AUDIO_URL",
        "https://github.com/parsaparsayi/crispy-funicular/releases/download/v1/output.mp3"
    )

def _env_default_image():
    # Prefer hosting your own image (e.g., release asset). Fallback is a public placeholder.
    return os.getenv("DEFAULT_IMAGE_URL", "https://raw.githubusercontent.com/github/explore/main/topics/python/python.png")

DEFAULT_IMAGE_URL = _env_default_image()
DEFAULT_AUDIO_URL = _env_default_audio()

def show_defaults():
    print(f"Output directory           : {OUTPUT_DIR}")
    print(f"Current default image URL  : {DEFAULT_IMAGE_URL}")
    print(f"Current default audio URL  : {DEFAULT_AUDIO_URL}")

def update_default_audio_url_runtime(new_url: str):
    """Update in-memory default audio URL after a successful upload."""
    global DEFAULT_AUDIO_URL
    if new_url and new_url.lower().startswith("https://") and new_url.lower().endswith(".mp3"):
        DEFAULT_AUDIO_URL = new_url
        print("Default audio URL updated:", DEFAULT_AUDIO_URL)
    else:
        print("Provided URL is not a valid https .mp3. Keeping previous default.")

# ------------------------------ HTTP session with retry ------------------------------
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def vpn_session():
    """
    Requests session with retry policy.
    trust_env=False ignores system proxies (useful if routing through a VPN client).
    User-Agent is descriptive to satisfy strict hosts (e.g., Wikimedia).
    """
    s = requests.Session()
    s.trust_env = False
    s.headers.update({
        "User-Agent": "virtual-avatar-pipeline/1.0 (+contact: example@example.com)",
        "Accept": "application/json, */*;q=0.5"
    })
    retry = Retry(
        total=4,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST")
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

# ------------------------------ Helpers ------------------------------
def load_voice_id():
    if os.path.exists(VOICE_ID_PATH):
        vid = open(VOICE_ID_PATH, "r", encoding="utf-8").read().strip()
        print(f"voice_id loaded: {vid}")
        return vid
    print(f"voice_id.txt not found at {VOICE_ID_PATH}. Use option 6 to clone or write a voice_id there.")
    return None

def set_elevenlabs_key_runtime(new_key: str):
    """Allow runtime override of ELEVENLABS_API_KEY."""
    global ELEVENLABS_API_KEY
    new_key = (new_key or "").strip()
    if new_key:
        ELEVENLABS_API_KEY = new_key
        os.environ["ELEVENLABS_API_KEY"] = new_key
        print("ELEVENLABS_API_KEY updated for this run.")
    else:
        print("Empty key ignored.")

def _timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

# ------------------------------ Phase 1: Voice cloning (ElevenLabs) ------------------------------
def clone_voice(name="MyVoice"):
    if not ELEVENLABS_API_KEY:
        print("Missing ELEVENLABS_API_KEY")
        return None
    if not os.path.exists(VOICE_SAMPLE_PATH):
        print(f"Sample not found: {VOICE_SAMPLE_PATH}")
        return None

    url = "https://api.elevenlabs.io/v1/voices/add"
    files = {"files": open(VOICE_SAMPLE_PATH, "rb")}
    data  = {"name": name, "description": "Cloned voice for avatar"}

    s = vpn_session()
    try:
        r = s.post(url, headers={"xi-api-key": ELEVENLABS_API_KEY}, data=data, files=files, timeout=90)
    except requests.exceptions.SSLError as e:
        print("TLS/VPN error reaching ElevenLabs. Try a different VPN location or disable split tunneling.")
        print(e)
        return None
    except requests.exceptions.RequestException as e:
        print("Network error cloning voice:", e)
        return None

    if r.ok and r.json().get("voice_id"):
        voice_id = r.json()["voice_id"]
        open(VOICE_ID_PATH, "w", encoding="utf-8").write(voice_id)
        print(f"Voice cloned and saved to {VOICE_ID_PATH}: {voice_id}")
        return voice_id

    print("Clone error:", r.status_code, (r.text or "")[:400])
    if r.status_code == 401 and "missing_permissions" in r.text:
        print("API key lacks 'voices_write'. Clone in ElevenLabs dashboard and put the voice_id into voice_id.txt.")
    if r.status_code == 401 and "invalid_api_key" in r.text:
        print("API key invalid. Use option 7 to paste a fresh key and retry.")
    return None

# ------------------------------ Phase 2: Persona chat (Groq) ------------------------------
def build_persona_prompt():
    return f"""
You are the user's personal voice and persona.

Your fixed identity:
- Full name: {USER_NAME}
- Birthdate: {USER_BIRTHDATE}
- City: {USER_CITY}

Style & constraints:
- Warm, clear, concise.
- Do not change name, age, or birthplace. If asked "What is your name?", answer "{USER_NAME}".
- If asked about your city or origin, answer "{USER_CITY}".
- Prefer English unless the user uses Persian; match Persian when used.
- Keep facts consistent with the identity above.

Additional background (non-binding flavor):
- {USER_BIO}
""".strip()

try:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
except Exception:
    groq_client = None

def chat_like_me(prompt):
    if not groq_client:
        return "Missing GROQ_API_KEY (or groq package)."
    system_msg = build_persona_prompt()
    msgs = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt}
    ]
    resp = groq_client.chat.completions.create(
        model="llama3-8b-8192",
        messages=msgs,
        temperature=0.4,
        max_tokens=512
    )
    return resp.choices[0].message.content

# ------------------------------ Phase 3: TTS (ElevenLabs) ------------------------------
def generate_tts(voice_id, text):
    if not ELEVENLABS_API_KEY:
        print("Missing ELEVENLABS_API_KEY")
        return None
    if not voice_id:
        print("No voice_id")
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }

    s = vpn_session()
    try:
        r = s.post(url, headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
                   json=payload, timeout=60)
    except requests.exceptions.SSLError as e:
        print("TLS/VPN error reaching ElevenLabs. Try another VPN region or disable split tunneling.")
        print(e)
        return None
    except requests.exceptions.RequestException as e:
        print("Network error during TTS:", e)
        return None

    if r.ok:
        with open(OUTPUT_MP3, "wb") as f:
            f.write(r.content)
        print(f"Audio saved: {OUTPUT_MP3} ({len(r.content)} bytes)")
        return OUTPUT_MP3

    print("TTS error:", r.status_code, (r.text or "")[:400])
    if r.status_code == 403:
        print("Likely geoblock. Ensure VPN routes all apps (no split tunneling). Try another region.")
    if r.status_code == 401:
        print("Invalid or expired API key. Use option 7 to paste a new ELEVENLABS_API_KEY and retry.")
    return None

# ------------------------------ FFmpeg helpers ------------------------------
_PLACEHOLDER_PNG_B64 = (
    # tiny 1x1 transparent PNG (base64)
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQAB"
    "J7n6WQAAAABJRU5ErkJggg=="
)

def _write_placeholder_png() -> str:
    path = os.path.join(tempfile.gettempdir(), "avatar_placeholder.png")
    with open(path, "wb") as f:
        f.write(base64.b64decode(_PLACEHOLDER_PNG_B64))
    return path

def _download_to_temp(url: str, suffix: str) -> str:
    s = vpn_session()
    r = s.get(url, stream=True, timeout=60)
    r.raise_for_status()
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(tmp_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
    return tmp_path

def _ensure_local_audio(mp3_path_or_url: str) -> str:
    """
    Return a local, short-path MP3 file for FFmpeg.
    - If URL: download to OUTPUT_DIR/audio_tmp.mp3
    - If local path: copy to OUTPUT_DIR/audio_tmp.mp3 (avoids quoting/long-path issues)
    """
    target = os.path.join(OUTPUT_DIR, "audio_tmp.mp3")
    try:
        if isinstance(mp3_path_or_url, str) and mp3_path_or_url.lower().startswith("https://"):
            s = vpn_session()
            r = s.get(mp3_path_or_url, stream=True, timeout=60)
            r.raise_for_status()
            with open(target, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            return target
        shutil.copyfile(mp3_path_or_url, target)
        return target
    except Exception as e:
        raise RuntimeError(f"Could not prepare local audio file: {e}")

def _ffmpeg_output_path(kind: str = "still") -> str:
    # kind: "still" or "did"
    ts = _timestamp()
    name = f"{kind}_{ts}.mp4"
    return os.path.join(OUTPUT_DIR, name)

def _run_ffmpeg(img_in: str, aud_in: str, out_path: str) -> bool:
    """
    Build FFmpeg args as a list (no shlex) to avoid Windows quoting issues.
    Also scale to even dimensions for H.264 compatibility.
    """
    vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    args = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-r", "25",
        "-i", img_in,
        "-i", aud_in,
        "-vf", vf,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-shortest",
        out_path,
    ]
    print("Running FFmpeg:", " ".join(f'"{a}"' if " " in a else a for a in args))
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode == 0 and os.path.exists(out_path):
        return True
    print("FFmpeg failed (return code", p.returncode, "):")
    print((p.stderr or "")[:2000])
    return False

# ------------------------------ FFmpeg fallback (image + audio -> mp4) ------------------------------
def fallback_ffmpeg_still_video(image_url_https: str, mp3_path_or_url: str, out_path=None):
    """
    Create a simple still-image MP4 using FFmpeg.
    - Writes to OUTPUT_DIR (or temp) to avoid Windows MAX_PATH issues.
    - Tries URL directly first, then downloads to temp if needed.
    - Falls back to a tiny local placeholder PNG as last resort.
    - Ensures audio is a short local file before calling FFmpeg.
    Returns the local path to the created video or None on failure.
    """
    if out_path is None:
        out_path = _ffmpeg_output_path("still")

    # Ensure audio is local and short
    local_audio = _ensure_local_audio(mp3_path_or_url)

    # Candidate images: requested/default first, then placeholder
    candidates = []
    if image_url_https:
        candidates.append(image_url_https)
    if DEFAULT_IMAGE_URL and DEFAULT_IMAGE_URL not in candidates:
        candidates.append(DEFAULT_IMAGE_URL)
    candidates.append(_write_placeholder_png())  # guaranteed local

    for idx, img in enumerate(candidates, 1):
        print(f"Trying image candidate {idx}/{len(candidates)}: {img}")

        # 1) Try FFmpeg directly with the URL/path
        if _run_ffmpeg(img, local_audio, out_path):
            print("Fallback video created:", out_path)
            return out_path

        # 2) If it's an https URL, try downloading then FFmpeg
        local_img = None
        try:
            if isinstance(img, str) and img.lower().startswith("https://"):
                local_img = _download_to_temp(img, suffix=os.path.splitext(img)[1] or ".png")
                if _run_ffmpeg(local_img, local_audio, out_path):
                    print("Fallback video created:", out_path)
                    return out_path
        except requests.exceptions.RequestException as e:
            print(f"Download failed for {img}: {e}")
        finally:
            if local_img and os.path.exists(local_img):
                try:
                    os.remove(local_img)
                except Exception:
                    pass

    print("All image candidates failed. Could not create video.")
    return None

# ------------------------------ Phase 4: D-ID animation ------------------------------
def _is_https_mp3(u: str) -> bool:
    """Return True for a public https .mp3 URL."""
    return isinstance(u, str) and u.lower().startswith("https://") and u.lower().endswith(".mp3")

def _save_remote_video(url: str, talk_id: str) -> str | None:
    """
    Download the remote D-ID video to OUTPUT_DIR so the GUI can show it
    under 'Recent Videos'. Returns local path or None.
    """
    try:
        s = vpn_session()
        r = s.get(url, stream=True, timeout=120)
        r.raise_for_status()
        local_path = os.path.join(OUTPUT_DIR, f"did_tlk_{talk_id}.mp4")
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        print("D-ID video saved locally:", local_path)
        return local_path
    except Exception as e:
        print("Could not save remote D-ID video locally:", e)
        return None

def animate_avatar_did(image_url, audio_url):
    """
    If audio_url is a public https .mp3, call D-ID and try to save the result locally.
    Otherwise, if local output.mp3 exists, build a still-image video locally.
    Returns a local file path (preferred) or a remote video URL (fallback) or None.
    """
    use_https_mp3 = _is_https_mp3(audio_url)

    if not use_https_mp3:
        # No usable https .mp3 -> fall back to local still video
        if os.path.exists(OUTPUT_MP3):
            print("No valid https .mp3 provided; using local output.mp3 with FFmpeg fallback.")
            return fallback_ffmpeg_still_video(image_url or DEFAULT_IMAGE_URL, OUTPUT_MP3)
        else:
            print("Need a public https .mp3 URL or a local output.mp3 first (run option 2).")
            return None

    # From here we have a valid https .mp3
    if not DID_AUTH:
        print("Missing DID_AUTH")
        return None
    if not (image_url and isinstance(image_url, str) and image_url.lower().startswith("https://")):
        print("D-ID requires an https image URL.")
        return None

    basic = base64.b64encode(DID_AUTH.encode()).decode()
    headers = {"Authorization": f"Basic {basic}", "Content-Type": "application/json", "Accept": "application/json"}
    payload = {"source_url": image_url, "script": {"type": "audio", "audio_url": audio_url}}

    try:
        r = requests.post("https://api.d-id.com/talks", headers=headers, json=payload, timeout=60)
    except requests.exceptions.RequestException as e:
        print("D-ID network error:", e)
        # Prefer the provided https audio for fallback (downloaded to local before ffmpeg runs)
        return fallback_ffmpeg_still_video(image_url, audio_url)

    if r.status_code >= 500:
        print("D-ID 5xx; using FFmpeg fallback.")
        return fallback_ffmpeg_still_video(image_url, audio_url)

    if not r.ok:
        print("Create failed:", r.status_code, (r.text or "")[:400])
        return None

    talk_id = r.json().get("id") or r.json().get("talk_id")
    print("Talk created:", talk_id)

    # Poll until done or timeout
    start = time.time()
    while time.time() - start < 240:
        try:
            g = requests.get(f"https://api.d-id.com/talks/{talk_id}", headers=headers, timeout=30)
        except requests.exceptions.RequestException as e:
            print("Poll error:", e)
            break
        if g.ok:
            data = g.json()
            status = data.get("status")
            if status == "done":
                url = data.get("result_url") or data.get("video_url")
                print("Video ready:", url)
                # Try to save locally for the GUI list
                local = _save_remote_video(url, talk_id)
                return local or url
            if status in ("error", "failed"):
                print("Render failed:", data)
                return None
        time.sleep(3)

    print("Timed out waiting for D-ID render.")
    return None

# ------------------------------ GitHub release helpers ------------------------------
def _gh_headers():
    if not GITHUB_TOKEN:
        raise RuntimeError("Missing GITHUB_TOKEN in .env")
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

def _split_repo(repo: str):
    if not repo or "/" not in repo:
        raise RuntimeError("GITHUB_REPO must be in the form 'owner/repo'")
    owner, name = repo.split("/", 1)
    return owner, name

def ensure_release(repo: str, tag: str, name: str):
    """Return (release_id, upload_url_base, html_url). Create the release if tag doesn't exist."""
    owner, rname = _split_repo(repo)
    s = vpn_session()

    # Try to get existing release by tag
    url = f"https://api.github.com/repos/{owner}/{rname}/releases/tags/{tag}"
    r = s.get(url, headers=_gh_headers(), timeout=30)
    if r.status_code == 200:
        data = r.json()
        return data["id"], data["upload_url"].split("{")[0], data.get("html_url")
    if r.status_code != 404:
        raise RuntimeError(f"GitHub error fetching release: {r.status_code} {r.text[:200]}")

    # Otherwise create release
    url = f"https://api.github.com/repos/{owner}/{rname}/releases"
    payload = {"tag_name": tag, "name": name or tag, "draft": False, "prerelease": False}
    r = s.post(url, headers=_gh_headers(), json=payload, timeout=30)
    if not r.ok:
        raise RuntimeError(f"GitHub error creating release: {r.status_code} {r.text[:200]}")
    data = r.json()
    return data["id"], data["upload_url"].split("{")[0], data.get("html_url")

def upload_asset_to_release(repo: str, release_id: int, asset_path: str, asset_name: str = None):
    """Upload a file to the release and return the browser_download_url."""
    if not os.path.exists(asset_path):
        raise RuntimeError(f"Asset not found: {asset_path}")

    owner, rname = _split_repo(repo)
    s = vpn_session()

    # Remove existing asset with the same name (keeps release list clean)
    assets_url = f"https://api.github.com/repos/{owner}/{rname}/releases/{release_id}/assets"
    assets = s.get(assets_url, headers=_gh_headers(), timeout=30)
    if assets.ok:
        for a in assets.json():
            if a.get("name") == (asset_name or os.path.basename(asset_path)):
                del_url = a["url"]
                s.delete(del_url, headers=_gh_headers(), timeout=30)
                break

    upload_url = f"https://uploads.github.com/repos/{owner}/{rname}/releases/{release_id}/assets"
    params = {"name": asset_name or os.path.basename(asset_path)}
    headers = _gh_headers()
    headers["Content-Type"] = "audio/mpeg"
    with open(asset_path, "rb") as f:
        r = s.post(upload_url, headers=headers, params=params, data=f, timeout=120)
    if not r.ok:
        raise RuntimeError(f"GitHub upload failed: {r.status_code} {r.text[:200]}")
    data = r.json()
    return data.get("browser_download_url")

def upload_output_mp3_and_set_default():
    """Upload local output.mp3 to GitHub and set DEFAULT_AUDIO_URL to the returned public URL."""
    try:
        if not GITHUB_REPO:
            print("Missing GITHUB_REPO in .env")
            return None
        if not GITHUB_TOKEN:
            print("Missing GITHUB_TOKEN in .env (requires release/contents permissions)")
            return None
        if not os.path.exists(OUTPUT_MP3):
            print("No local output.mp3 to upload (run Option 2 first).")
            return None

        rid, _upl, _html = ensure_release(GITHUB_REPO, GITHUB_RELEASE_TAG, GITHUB_RELEASE_NAME)
        url = upload_asset_to_release(GITHUB_REPO, rid, OUTPUT_MP3, GITHUB_ASSET_NAME)
        if url and url.lower().endswith(".mp3"):
            update_default_audio_url_runtime(url)
            print("Upload complete. Default audio URL updated.")
            return url

        print("Upload returned an unexpected URL:", url)
        return url
    except Exception as e:
        print("Upload error:", e)
        return None

# ------------------------------ CLI Menu ------------------------------
def main():
    voice_id = load_voice_id()
    print("Using voice_id:", voice_id)
    show_defaults()

    while True:
        print("\nVirtual Avatar Menu")
        print("1. Chat in your personality")
        print("2. Convert text to speech (TTS)")
        print("3. Animate avatar (D-ID or local fallback)")
        print("4. Run full pipeline")
        print("5. Exit")
        print("6. Clone voice from sample")
        print("7. Paste a new ELEVENLABS_API_KEY (runtime)")
        print("8. Upload output.mp3 to GitHub Release (set as default)")
        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            q = input("Question: ")
            print("Reply:", chat_like_me(q))

        elif choice == "2":
            t = input("Text: ")
            mp3_path = generate_tts(voice_id, t)
            if mp3_path:
                auto = input("Upload to GitHub Release now? [y/N]: ").strip().lower()
                if auto == "y":
                    upload_output_mp3_and_set_default()

        elif choice == "3":
            img = input(f"Image URL (https) [Enter for default: {DEFAULT_IMAGE_URL}]: ").strip() or DEFAULT_IMAGE_URL
            prompt = f"Audio URL (.mp3, https) [Enter for default: {DEFAULT_AUDIO_URL} or leave blank to use local output.mp3]: "
            aud = input(prompt).strip()
            if not aud:
                # Prefer hosted default; otherwise, local fallback if output.mp3 exists
                if DEFAULT_AUDIO_URL:
                    aud = DEFAULT_AUDIO_URL
                elif os.path.exists(OUTPUT_MP3):
                    animate_avatar_did(img, None)
                    continue
                else:
                    print("No audio URL and no local output.mp3. Use option 2 first.")
                    continue
            animate_avatar_did(img, aud)

        elif choice == "4":
            q = input("Ask a question: ")
            reply = chat_like_me(q)
            print("Reply:", reply)
            mp3 = generate_tts(voice_id, reply)
            if mp3:
                auto = input("Upload new output.mp3 to GitHub Release and use it? [y/N]: ").strip().lower()
                if auto == "y":
                    upload_output_mp3_and_set_default()

            img = input(f"Image URL (https) [Enter for default: {DEFAULT_IMAGE_URL}]: ").strip() or DEFAULT_IMAGE_URL
            prompt = f"Public https .mp3 URL [Enter for default: {DEFAULT_AUDIO_URL} or leave blank to use local output.mp3]: "
            aud_url = input(prompt).strip()
            if not aud_url:
                aud_url = DEFAULT_AUDIO_URL if DEFAULT_AUDIO_URL else None
            if aud_url:
                animate_avatar_did(img, aud_url)
            else:
                animate_avatar_did(img, None)

        elif choice == "5":
            print("Exiting.")
            break

        elif choice == "6":
            new_name = input("Name for cloned voice (default MyVoice): ").strip() or "MyVoice"
            v = clone_voice(new_name)
            if v:
                voice_id = load_voice_id()
            else:
                print("Clone did not succeed. You can still use Option 2 (TTS) or Option 7 to paste a new API key.")

        elif choice == "7":
            pasted = input("Paste new ELEVENLABS_API_KEY: ").strip()
            set_elevenlabs_key_runtime(pasted)

        elif choice == "8":
            upload_output_mp3_and_set_default()

        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()


