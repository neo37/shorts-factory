"""Speech-to-text for voice-message prompts.

Primary backend: NVIDIA nemotron-3.5-asr-streaming-0.6b served behind an OpenAI-compatible
`/v1/audio/transcriptions` endpoint (config ASR_BASE_URL). Falls back to OpenAI Whisper if
configured. Heavy CPU work — always invoked from the Celery queue (concurrency=1), never inline.
"""
import logging
from pathlib import Path

import requests
from config import Config

log = logging.getLogger("videobot.asr")


def _asr_server(audio_path):
    url = Config.ASR_BASE_URL.rstrip("/") + "/audio/transcriptions"
    with open(audio_path, "rb") as f:
        r = requests.post(url, files={"file": (Path(audio_path).name, f)},
                          data={"model": Config.ASR_MODEL}, timeout=Config.ASR_TIMEOUT)
    r.raise_for_status()
    try:
        return (r.json() or {}).get("text", "").strip()
    except ValueError:
        return r.text.strip()


def _openai_whisper(audio_path):
    from openai import OpenAI
    if not Config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=Config.OPENAI_API_KEY)
    with open(audio_path, "rb") as f:
        tr = client.audio.transcriptions.create(model="whisper-1", file=f)
    return (tr.text or "").strip()


def transcribe(audio_path):
    """Return transcribed text. Tries the nemotron ASR server, then OpenAI Whisper."""
    for name, fn in (("nemotron", _asr_server), ("openai-whisper", _openai_whisper)):
        try:
            text = fn(audio_path)
            if text:
                log.info("ASR ok via %s (%d chars)", name, len(text))
                return text
        except Exception as e:  # noqa: BLE001
            log.warning("ASR backend %s failed: %s", name, e)
    raise RuntimeError("all ASR backends failed")
