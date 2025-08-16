import os
from flask import Flask, request, jsonify, send_from_directory, render_template
import grok  # uses your existing pipeline functions

app = Flask(__name__)

# Always use the same OUTPUT_DIR as grok.py
OUTPUT_DIR = grok.OUTPUT_DIR
os.makedirs(OUTPUT_DIR, exist_ok=True)

def _list_videos():
    files = []
    for name in sorted(os.listdir(OUTPUT_DIR)):
        if name.lower().endswith(".mp4"):
            files.append(name)
    return files

@app.route("/")
def index():
    # Prefer live values from grok module; fall back to environment, then empty.
    default_image = (getattr(grok, "DEFAULT_IMAGE_URL", None)
                     or os.getenv("DEFAULT_IMAGE_URL", ""))
    default_audio = (getattr(grok, "DEFAULT_AUDIO_URL", None)
                     or os.getenv("DEFAULT_AUDIO_URL", ""))

    defaults = {
        "image_url": default_image,
        "audio_url": default_audio,
        "output_dir": OUTPUT_DIR,
    }
    return render_template("index.html", defaults=defaults, videos=_list_videos())

@app.route("/media/<path:filename>")
def media(filename):
    # serve from OUTPUT_DIR so you can play the videos in-browser
    return send_from_directory(OUTPUT_DIR, filename)

@app.post("/tts")
def tts():
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    upload = bool(data.get("upload", True))
    voice_id = grok.load_voice_id()
    if not text:
        return jsonify(ok=False, error="Text is empty"), 400
    if not voice_id:
        return jsonify(ok=False, error="No voice_id; run Option 6 in CLI once."), 400

    mp3_path = grok.generate_tts(voice_id, text)
    url = None
    if mp3_path and upload:
        url = grok.upload_output_mp3_and_set_default()
        # Propagate to the process env so a page reload reflects the new default
        if url:
            os.environ["DEFAULT_AUDIO_URL"] = url
    return jsonify(ok=bool(mp3_path), mp3=mp3_path, uploaded_url=url)

@app.post("/animate")
def animate():
    data = request.get_json(force=True)
    # Prefer live defaults from grok for better UX
    default_image = (getattr(grok, "DEFAULT_IMAGE_URL", None)
                     or os.getenv("DEFAULT_IMAGE_URL", ""))
    image_url = (data.get("image_url") or "").strip() or default_image

    # If client sends empty audio_url, that means "use local output.mp3" (fallback)
    audio_url = (data.get("audio_url") or "").strip()

    local_path_or_url = grok.animate_avatar_did(image_url, audio_url)
    ok = bool(local_path_or_url)
    # If a local file was created, expose basename so UI can play it
    basename = None
    if ok and isinstance(local_path_or_url, str) and os.path.exists(local_path_or_url):
        basename = os.path.basename(local_path_or_url)
    return jsonify(ok=ok, result=local_path_or_url, basename=basename)

@app.post("/full")
def full():
    data = request.get_json(force=True)
    question = data.get("question", "").strip()
    upload = bool(data.get("upload", True))

    default_image = (getattr(grok, "DEFAULT_IMAGE_URL", None)
                     or os.getenv("DEFAULT_IMAGE_URL", ""))
    image_url = (data.get("image_url") or "").strip() or default_image

    if not question:
        return jsonify(ok=False, error="Question is empty"), 400

    # Persona answer
    answer = grok.chat_like_me(question)
    if not answer:
        return jsonify(ok=False, error="No answer generated"), 500

    # TTS
    voice_id = grok.load_voice_id()
    if not voice_id:
        return jsonify(ok=False, error="No voice_id; run Option 6 in CLI once."), 400
    mp3_path = grok.generate_tts(voice_id, answer)
    if not mp3_path:
        return jsonify(ok=False, error="TTS failed"), 500

    if upload:
        url = grok.upload_output_mp3_and_set_default()
        if url:
            os.environ["DEFAULT_AUDIO_URL"] = url
        audio_url = url or ""
    else:
        audio_url = ""  # force local fallback with output.mp3

    # Animate
    video_result = grok.animate_avatar_did(image_url, audio_url)
    basename = os.path.basename(video_result) if (isinstance(video_result, str) and os.path.exists(video_result)) else None

    return jsonify(ok=bool(video_result), question=question, answer=answer, mp3=mp3_path,
                   result=video_result, basename=basename)

if __name__ == "__main__":
    # Run on localhost:5000
    app.run(debug=True)


