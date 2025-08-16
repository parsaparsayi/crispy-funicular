import os
from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.exceptions import HTTPException
import grok  # your pipeline functions live here

app = Flask(__name__)
app.secret_key = "dev"  # local use only

# Use the exact same output directory as grok.py
OUTPUT_DIR = grok.OUTPUT_DIR
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------- helpers ----------------------------
def _list_videos():
    """Newest first, for the Recent Videos panel."""
    if not os.path.isdir(OUTPUT_DIR):
        return []
    files = [f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith(".mp4")]
    files.sort(key=lambda name: os.path.getmtime(os.path.join(OUTPUT_DIR, name)), reverse=True)
    return files


def _is_https_mp3(u: str) -> bool:
    return isinstance(u, str) and u.lower().startswith("https://") and u.lower().endswith(".mp3")


# If anything unexpected happens, return JSON (not an HTML error page)
@app.errorhandler(Exception)
def _json_errors(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    return jsonify(ok=False, error=e.__class__.__name__, detail=str(e)), code


# ---------------------------- routes ----------------------------
@app.route("/")
def index():
    defaults = {
        # use grok's in-memory defaults (reflects Option 8 uploads)
        "image_url": getattr(grok, "DEFAULT_IMAGE_URL", os.getenv("DEFAULT_IMAGE_URL", "")),
        "audio_url": getattr(grok, "DEFAULT_AUDIO_URL", os.getenv("DEFAULT_AUDIO_URL", "")),
        "output_dir": OUTPUT_DIR,
    }
    return render_template("index.html", defaults=defaults, videos=_list_videos())


@app.route("/media/<path:filename>")
def media(filename):
    """Serve generated videos from OUTPUT_DIR so the GUI can play them."""
    return send_from_directory(OUTPUT_DIR, filename)


@app.post("/tts")
def tts():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    upload = bool(data.get("upload", True))

    if not text:
        return jsonify(ok=False, error="BadRequest", detail="Text is empty"), 400

    voice_id = grok.load_voice_id()
    if not voice_id:
        return jsonify(ok=False, error="NoVoiceId", detail="Put voice_id.txt next to grok.py or run CLI Option 6"), 400

    try:
        mp3_path = grok.generate_tts(voice_id, text)
    except Exception as e:
        return jsonify(ok=False, error="TTSException", detail=str(e)), 500

    if not mp3_path:
        return jsonify(ok=False, error="TTSFailed", detail="generate_tts returned None"), 500

    uploaded_url = None
    if upload:
        try:
            uploaded_url = grok.upload_output_mp3_and_set_default()
        except Exception as e:
            # Don't fail the request if upload fails; just report it
            uploaded_url = None

    return jsonify(ok=True, mp3=mp3_path, uploaded_url=uploaded_url)


@app.post("/animate")
def animate():
    data = request.get_json(force=True, silent=True) or {}
    # If blank, use DEFAULT_IMAGE_URL
    image_url = (data.get("image_url") or "").strip() or getattr(grok, "DEFAULT_IMAGE_URL", os.getenv("DEFAULT_IMAGE_URL", ""))
    # If "", grok.animate_avatar_did will fall back to local output.mp3 (still video)
    audio_url = (data.get("audio_url") or "").strip()

    try:
        result = grok.animate_avatar_did(image_url, audio_url)
    except Exception as e:
        return jsonify(ok=False, error="AnimateException", detail=str(e)), 500

    ok = bool(result)
    basename = None
    if ok and isinstance(result, str) and os.path.exists(result):
        basename = os.path.basename(result)

    return jsonify(ok=ok, result=result, basename=basename)


@app.post("/full")
def full():
    data = request.get_json(force=True, silent=True) or {}
    question = (data.get("question") or "").strip()
    upload = bool(data.get("upload", True))
    image_url = (data.get("image_url") or "").strip() or getattr(grok, "DEFAULT_IMAGE_URL", os.getenv("DEFAULT_IMAGE_URL", ""))

    if not question:
        return jsonify(ok=False, error="BadRequest", detail="Question is empty"), 400

    # 1) Persona answer
    try:
        answer = grok.chat_like_me(question)
    except Exception as e:
        return jsonify(ok=False, error="GroqException", detail=str(e)), 500
    if not answer:
        return jsonify(ok=False, error="NoAnswer", detail="No answer from chat_like_me"), 500

    # 2) TTS
    voice_id = grok.load_voice_id()
    if not voice_id:
        return jsonify(ok=False, error="NoVoiceId", detail="Put voice_id.txt next to grok.py or run CLI Option 6"), 400
    try:
        mp3_path = grok.generate_tts(voice_id, answer)
    except Exception as e:
        return jsonify(ok=False, error="TTSException", detail=str(e)), 500
    if not mp3_path:
        return jsonify(ok=False, error="TTSFailed", detail="generate_tts returned None"), 500

    # 3) Choose audio for animation
    # If user opted to upload, let grok upload the freshly-made MP3, then use the new https URL.
    # If not uploading, but a valid DEFAULT_AUDIO_URL already exists, use it (D-ID).
    # Otherwise pass "" to force local FFmpeg still-video fallback.
    if upload:
        try:
            grok.upload_output_mp3_and_set_default()
            audio_url = getattr(grok, "DEFAULT_AUDIO_URL", os.getenv("DEFAULT_AUDIO_URL", ""))
        except Exception:
            audio_url = ""
    else:
        existing = getattr(grok, "DEFAULT_AUDIO_URL", os.getenv("DEFAULT_AUDIO_URL", ""))
        audio_url = existing if _is_https_mp3(existing) else ""

    # 4) Animate
    try:
        video_result = grok.animate_avatar_did(image_url, audio_url)
    except Exception as e:
        return jsonify(ok=False, error="AnimateException", detail=str(e)), 500

    basename = os.path.basename(video_result) if (isinstance(video_result, str) and os.path.exists(video_result)) else None

    return jsonify(ok=bool(video_result), question=question, answer=answer,
                   mp3=mp3_path, result=video_result, basename=basename)


if __name__ == "__main__":
    # Run on localhost:5000
    app.run(debug=True)




