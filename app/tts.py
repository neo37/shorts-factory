"""TTS layer. Backs the OpenAI-compatible /v1/audio/speech endpoint.

Backend preference (config TTS_BACKEND, default auto): kokoro -> piper -> openai.
Handles the special stress for the product name: 'бизнес-пад' -> 'бизнес-па́д' (stress on 'пад').
"""
import logging
import re
import subprocess
import tempfile
from pathlib import Path

import requests
from config import Config

log = logging.getLogger("videobot.tts")

# combining acute accent on the vowel of "пад"
_BP_STRESSED = "бизнес-па́д"
_BP_PATTERNS = [
    re.compile(r"business[-\s]?pad", re.IGNORECASE),
    re.compile(r"бизнес[-\s]?пад", re.IGNORECASE),
]


def apply_pronunciation(text: str) -> str:
    out = text
    for pat in _BP_PATTERNS:
        out = pat.sub(_BP_STRESSED, out)
    return out


# gender -> per-backend voice ids
_VOICE_MAP = {
    "openai": {"female": "nova", "male": "onyx", "neutral": "sage"},
    "kokoro": {"female": "af_bella", "male": "am_adam", "neutral": "af_sarah"},
}


def _resolve_voice(backend, voice, gender):
    if voice:  # explicit voice id wins
        return voice
    return _VOICE_MAP.get(backend, {}).get(gender or "female", "female")


def _synth_kokoro(text, voice, out_path, fmt):
    url = Config.KOKORO_BASE_URL.rstrip("/") + "/audio/speech"
    r = requests.post(url, json={"model": "kokoro", "input": text, "voice": voice,
                                 "response_format": fmt}, timeout=120)
    r.raise_for_status()
    Path(out_path).write_bytes(r.content)


def _synth_piper(text, gender, out_path, fmt):
    voice = Config.PIPER_VOICE_FEMALE if gender != "male" else Config.PIPER_VOICE_MALE
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav = tmp.name
    subprocess.run([Config.PIPER_BIN, "--model", voice, "--output_file", wav],
                   input=text.encode(), check=True)
    if fmt == "wav":
        Path(out_path).write_bytes(Path(wav).read_bytes())
    else:
        subprocess.run(["ffmpeg", "-y", "-i", wav, "-b:a", "192k", str(out_path),
                        "-loglevel", "error"], check=True)
    Path(wav).unlink(missing_ok=True)


def _synth_openai(text, voice, out_path, fmt):
    from openai import OpenAI
    if not Config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=Config.OPENAI_API_KEY)
    instr = ("Speak in Russian. Clear, confident, natural pacing. Read any stress marks "
             "(combining accents) as written.")
    model = "gpt-4o-mini-tts"
    # `instructions` is only supported on newer SDKs/models — degrade gracefully.
    for kwargs in ({"instructions": instr}, {}):
        try:
            with client.audio.speech.with_streaming_response.create(
                model=model, voice=voice, input=text, response_format=fmt, **kwargs,
            ) as resp:
                resp.stream_to_file(out_path)
            return
        except TypeError:
            continue  # SDK doesn't accept `instructions` — retry without it
        except Exception:
            # instructions rejected by the model/endpoint → fall back to plain call
            if kwargs:
                continue
            raise


def synthesize(text, out_path, voice=None, gender="female", fmt="mp3"):
    """Synthesize speech to out_path. Returns the backend actually used."""
    text = apply_pronunciation(text)
    order = (["kokoro", "piper", "openai"] if Config.TTS_BACKEND == "auto"
             else [Config.TTS_BACKEND])
    last_err = None
    for backend in order:
        try:
            if backend == "kokoro":
                _synth_kokoro(text, _resolve_voice("kokoro", voice, gender), out_path, fmt)
            elif backend == "piper":
                _synth_piper(text, gender, out_path, fmt)
            elif backend == "openai":
                _synth_openai(text, _resolve_voice("openai", voice, gender), out_path, fmt)
            else:
                raise RuntimeError(f"unknown TTS backend {backend}")
            log.info("TTS ok via %s -> %s", backend, out_path)
            return backend
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning("TTS backend %s failed: %s", backend, e)
    raise RuntimeError(f"all TTS backends failed: {last_err}")
