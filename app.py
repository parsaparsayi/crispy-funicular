import os
from flask import Flask, request, jsonify, send_from_directory, render_template
import grok  # uses your existing pipeline functions

app = Flask(__name__)
app.secret_key = "dev"  # local use only

# Always use the same OUTPUT_DIR as grok.py
OUTPUT_DIR = grok.OUTPUT_DIR
os.makedirs(OUTPUT_DIR, exist_ok=True)

def _list_videos():
    if not os.path.isdir(OUTPUT_DIR):
        return []
    files = [f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith(".mp4")]
    # Newest first
    files.sort(key=lambda name: os.path.getmtime(os.path.join(OUTPUT_DIR, name)), reverse=True)
    return files

@app.route("/")
def index():
    defaults = {
        # Use grok's in-memory defaults so Option 8 updates are reflected immediately
        "image_url": getattr(grok, "DEFAULT_IMAGE_URL", os.getenv("DEFAULT_IMAGE_URL", "")),
        "audio_url": getattr(grok, "DEFAULT_AUDIO_URL", os.getenv("DEFAULT_AUDIO_URL", "")),
        "output_dir": OUTPUT_DIR,
    }
    return render_template("index.html", defaults=defaults, videos=_list_videos())

@app.route("/media/<path:filename>")
def media(filename):
    # serve from OUTPUT_DIR so you can play videos in-browser
    return send_from_directory(OUTPUT_DIR, filename)

@app.post("/tts")
def tts():
    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()
    upload = bool(data.get("upload", True))
    if not text:
        return jsonify(ok=False, error="Text is empty"), 400

    voice_id = grok.load_voice_id()
    if not voice_id:
        return jsonify(ok=False, error="No voice_id; run CLI Option 6 once or put voice_id.txt next to grok.py."), 400

    mp3_path = grok.generate_tts(voice_id, text)
    url = None
    if mp3_path and upload:
        url = grok.upload_output_mp3_and_set_default()
    return jsonify(ok=bool(mp3_path), mp3=mp3_path, uploaded_url=url)

@app.post("/animate")
def animate():
    data = request.get_json(force=True)
    image_url = (data.get("image_url") or "").strip() or getattr(grok, "DEFAULT_IMAGE_URL", os.getenv("DEFAULT_IMAGE_URL", ""))
    # If audio_url is "", grok.animate_avatar_did will prefer local output.mp3 (FFmpeg fallback)
    audio_url = (data.get("audio_url") or "").strip()
    result = grok.animate_avatar_did(image_url, audio_url)
    ok = bool(result)
    basename = None
    if ok and isinstance(result, str) and os.path.exists(result):
        basename = os.path.basename(result)
    return jsonify(ok=ok, result=result, basename=basename)

@app.post("/full")
def full():
    data = request.get_json(force=True)
    question = (data.get("question") or "").strip()
    upload = bool(data.get("upload", True))
    image_url = (data.get("image_url") or "").strip() or getattr(grok, "DEFAULT_IMAGE_URL", os.getenv("DEFAULT_IMAGE_URL", ""))

    if not question:
        return jsonify(ok=False, error="Question is empty"), 400

    # Persona answer
    answer = grok.chat_like_me(question)
    if not answer:
        return jsonify(ok=False, error="No answer generated"), 500

    # TTS
    voice_id = grok.load_voice_id()
    if not voice_id:
        return jsonify(ok=False, error="No voice_id; run CLI Option 6 once or put voice_id.txt next to grok.py."), 400
    mp3_path = grok.generate_tts(voice_id, answer)
    if not mp3_path:
        return jsonify(ok=False, error="TTS failed"), 500

    # If upload, grok will update its in-memory DEFAULT_AUDIO_URL; use that, not os.getenv
    if upload:
        grok.upload_output_mp3_and_set_default()
        audio_url = getattr(grok, "DEFAULT_AUDIO_URL", os.getenv("DEFAULT_AUDIO_URL", ""))
    else:
        audio_url = ""  # force local fallback with output.mp3

    # Animate
    video_result = grok.animate_avatar_did(image_url, audio_url)
    basename = os.path.basename(video_result) if (isinstance(video_result, str) and os.path.exists(video_result)) else None

    return jsonify(ok=bool(video_result), question=question, answer=answer,
                   mp3=mp3_path, result=video_result, basename=basename)

if __name__ == "__main__":
    # Run on localhost:5000
    app.run(debug=True)
