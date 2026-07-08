"""External OpenAI-compatible API (Bearer <api_key> from the ApiKey table).

  POST /v1/chat/completions -> proxied to Ollama (uncensored model)
  POST /v1/audio/speech     -> TTS engine (supports бизнес-пáд stress, male/female)
"""
import io
import logging

import requests
from flask import Blueprint, Response, jsonify, request

from config import Config
from .models import ApiKey
from . import tts

log = logging.getLogger("videobot.api")
api_bp = Blueprint("api", __name__)


def _auth_ok():
    hdr = request.headers.get("Authorization", "")
    if not hdr.startswith("Bearer "):
        return False
    key = hdr[len("Bearer "):].strip()
    row = ApiKey.query.filter_by(key=key, is_active=True).first()
    return row is not None


def _unauth():
    return jsonify({"error": {"message": "invalid api key", "type": "auth"}}), 401


@api_bp.post("/v1/chat/completions")
def chat_completions():
    if not _auth_ok():
        return _unauth()
    payload = request.get_json(force=True, silent=True) or {}
    payload.setdefault("model", Config.LLM_MODEL)
    url = Config.OLLAMA_BASE_URL.rstrip("/") + "/chat/completions"
    try:
        stream = bool(payload.get("stream"))
        r = requests.post(url, json=payload,
                          headers={"Authorization": f"Bearer {Config.OLLAMA_API_KEY}"},
                          timeout=Config.LLM_TIMEOUT, stream=stream)
        if stream:
            return Response(r.iter_content(chunk_size=None),
                            content_type=r.headers.get("Content-Type", "text/event-stream"))
        return Response(r.content, status=r.status_code,
                        content_type=r.headers.get("Content-Type", "application/json"))
    except Exception as e:  # noqa: BLE001
        log.exception("chat proxy failed")
        return jsonify({"error": {"message": f"upstream LLM error: {e}", "type": "upstream"}}), 502


@api_bp.post("/v1/audio/speech")
def audio_speech():
    if not _auth_ok():
        return _unauth()
    payload = request.get_json(force=True, silent=True) or {}
    text = payload.get("input", "")
    if not text:
        return jsonify({"error": {"message": "'input' required", "type": "invalid_request"}}), 400
    voice = payload.get("voice")               # explicit voice id (optional)
    gender = payload.get("gender", "female")   # female|male|neutral (custom extension)
    fmt = payload.get("response_format", "mp3")
    import tempfile
    from pathlib import Path
    with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as tmp:
        out = tmp.name
    try:
        tts.synthesize(text, out, voice=voice, gender=gender, fmt=fmt)
        data = Path(out).read_bytes()
        Path(out).unlink(missing_ok=True)
        mime = "audio/mpeg" if fmt == "mp3" else f"audio/{fmt}"
        return Response(io.BytesIO(data), content_type=mime)
    except Exception as e:  # noqa: BLE001
        log.exception("tts failed")
        return jsonify({"error": {"message": f"tts error: {e}", "type": "tts"}}), 502


@api_bp.post("/v1/audio/transcriptions")
def audio_transcriptions():
    """OpenAI-compatible STT. Heavy work runs on the single-thread Celery queue (never inline)."""
    if not _auth_ok():
        return _unauth()
    f = request.files.get("file")
    if not f:
        return jsonify({"error": {"message": "'file' required (multipart)", "type": "invalid_request"}}), 400
    import tempfile
    from pathlib import Path
    suffix = Path(f.filename or "audio.ogg").suffix or ".ogg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        path = tmp.name
    f.save(path)
    try:
        from .tasks import transcribe_audio
        res = transcribe_audio.delay(path)
        out = res.get(timeout=Config.ASR_TIMEOUT + 30)  # block on the queue result
        return jsonify(out)
    except Exception as e:  # noqa: BLE001
        log.exception("transcription failed")
        return jsonify({"error": {"message": f"asr error: {e}", "type": "asr"}}), 502
    finally:
        Path(path).unlink(missing_ok=True)


@api_bp.get("/v1/models")
def models():
    if not _auth_ok():
        return _unauth()
    return jsonify({"object": "list", "data": [
        {"id": Config.LLM_MODEL, "object": "model", "owned_by": "videobot"},
    ]})


@api_bp.get("/healthz")
def healthz():
    return jsonify({"ok": True})
