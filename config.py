"""Central configuration, environment-driven. See .env.example."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

def _bool(v, default=False):
    if v is None:
        return default
    return str(v).lower() in ("1", "true", "yes", "on")


class Config:
    # --- Flask / DB ---
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-prod")
    DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{(DATA_DIR / 'videobot.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Admin auth (Flask-Admin basic gate) ---
    ADMIN_USER = os.getenv("ADMIN_USER", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

    # --- Billing ---
    NEW_USER_CREDITS = int(os.getenv("NEW_USER_CREDITS", "100"))
    CREDITS_PER_VIDEO = int(os.getenv("CREDITS_PER_VIDEO", "1"))
    TOPUP_RUB = int(os.getenv("TOPUP_RUB", "500"))
    TOPUP_VIDEOS = int(os.getenv("TOPUP_VIDEOS", "5"))

    # --- Links / branding (permanent, non-erasable footer) ---
    PROJECT_FOOTER_URL = os.getenv("PROJECT_FOOTER_URL", "https://videos.ai3d.art")
    TOPUP_CONTACT_URL = os.getenv("TOPUP_CONTACT_URL", "https://t.me/kiselev_vasilli_andreevichd")

    # --- Web upload (for media larger than Telegram's ~20 MB bot limit) ---
    # Public base URL the bot puts in the upload link; must reach this Flask app.
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    MAX_WEB_UPLOAD_MB = int(os.getenv("MAX_WEB_UPLOAD_MB", "500"))
    UPLOAD_TOKEN_TTL_HOURS = int(os.getenv("UPLOAD_TOKEN_TTL_HOURS", "24"))

    # --- Celery / Redis ---
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
    # If Redis is unavailable locally, run tasks synchronously (dev only).
    CELERY_TASK_ALWAYS_EAGER = _bool(os.getenv("CELERY_TASK_ALWAYS_EAGER"), False)

    # --- LLM (Ollama, OpenAI-compatible) ---
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")  # ignored by Ollama
    LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:3b-instruct")
    LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))

    # --- TTS engine (OpenAI-compatible /v1/audio/speech backend) ---
    # Order of preference: kokoro -> piper -> openai
    TTS_BACKEND = os.getenv("TTS_BACKEND", "auto")  # auto|kokoro|piper|openai
    KOKORO_BASE_URL = os.getenv("KOKORO_BASE_URL", "http://localhost:8880/v1")
    PIPER_BIN = os.getenv("PIPER_BIN", "piper")
    PIPER_VOICE_FEMALE = os.getenv("PIPER_VOICE_FEMALE", "ru_RU-irina-medium")
    PIPER_VOICE_MALE = os.getenv("PIPER_VOICE_MALE", "ru_RU-ruslan-medium")
    # Fallback to OpenAI TTS if configured (reads OPENAI_API_KEY or OPEN_AI_KEY)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_KEY", "")

    # --- ASR (speech-to-text for voice-message prompts) ---
    # NVIDIA nemotron-3.5-asr-streaming-0.6b served behind an OpenAI-compatible endpoint.
    ASR_BASE_URL = os.getenv("ASR_BASE_URL", "http://localhost:8890/v1")
    ASR_MODEL = os.getenv("ASR_MODEL", "nvidia/nemotron-3.5-asr-streaming-0.6b")
    ASR_TIMEOUT = int(os.getenv("ASR_TIMEOUT", "120"))

    # --- OpenMontage rendering ---
    OPENMONTAGE_DIR = Path(os.getenv("OPENMONTAGE_DIR", BASE_DIR.parent))
    RENDER_QUALITY = os.getenv("RENDER_QUALITY", "high")
    RENDER_FPS = int(os.getenv("RENDER_FPS", "30"))
    # Rendering must stay single-threaded to avoid CPU overload (TZ §4).
    RENDER_CONCURRENCY = 1

    # --- Bots ---
    # Bot tokens & their design_style are stored in DB (Bot table), managed via admin.
    BOT_POLL_TIMEOUT = int(os.getenv("BOT_POLL_TIMEOUT", "30"))
