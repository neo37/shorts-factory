# VideoBot Platform

**Languages:** **English** · [Русский](README.ru.md) · [Српски](README.sr.md)
**Live landing:** https://videos.ai3d.art · **Get access / top-up:** [@kiselev_vasilli_andreevichd](https://t.me/kiselev_vasilli_andreevichd)

A multi-bot **SaaS platform** that turns a text prompt into a branded vertical **Short** (9:16).
Users chat with a Telegram bot, get a **storyboard + draft voice-over**, refine it in a loop, and on
approval the platform renders a finished video in a fixed design style — powered by **OpenMontage**
(HyperFrames/GSAP) for composition, an **LLM** (via Ollama) for scripting, and a
pluggable **TTS** engine for narration. It also exposes an **OpenAI-compatible API** so external
projects can reuse the same LLM and TTS.

> One bot = one design style. Rendering runs strictly single-threaded to protect the CPU.

---

## ✨ Features

- **Prompt → Short.** Free-form prompt → structured storyboard, scene captions and a narration draft.
- **Refinement loop.** Inline buttons: `✅ Approve · ✏️ Amend · ❌ Decline · 🎬 Examples · 💳 Top-up`.
  Amendments are free; a credit is charged only on the first prompt.
- **Text or voice prompts.** Send a text prompt or a **voice message** — voice is transcribed
  (NVIDIA nemotron ASR) and used as the prompt.
- **Media upload.** Users attach **photos & videos** (≤ 20 MB — Telegram Bot API `getFile` limit);
  media becomes scene backgrounds. Media source can be **user / external stock / mix**, grouped per **project**.
- **Single-thread queue.** All heavy CPU work — **rendering and speech recognition** — is serialized
  on one Celery worker (`concurrency=1`) so they never compete for the CPU.
- **Multi-bot.** Add many Telegram tokens; each bot is bound to one `design_style`.
- **Billing (credits).** New users get 100 credits; 1 video = 1 credit. `500 ₽ = 5 videos` (manual top-up).
- **Non-erasable footer.** Every message and rendered video carries `https://videos.ai3d.art`.
- **Demo watermark.** Shown until an admin marks the user as paid; the footer is always kept.
- **Admin panel** (Flask-Admin): bots, users/billing, presets, jobs and a **Celery queue manager**
  (cancel one task / purge the whole queue).
- **OpenAI-compatible API** with per-key auth: `POST /v1/chat/completions`, `POST /v1/audio/speech`
  (male/female voices, and the special stress `бизнес-пáд`), `POST /v1/audio/transcriptions`
  (nemotron ASR, routed through the queue), `GET /v1/models`.

## 🏗 Architecture

```
Telegram users ──► aiogram multibot ──► Flask (billing, jobs) ──► Celery+Redis queue (concurrency=1)
                                            │                          │
                                     Flask-Admin panel          1) LLM  → Ollama
                                            │                    2) TTS  → Kokoro / Piper / OpenAI
                                     SQLite (users, bots,        3) Render  → OpenMontage (HyperFrames)
                                     presets, jobs, api keys)          │
External apps ──► OpenAI-compatible /v1 API ──────────────────► videos.ai3d.art footer (permanent)
```

Target host **8 vCPU / 24 GB RAM**; peak ≈16.5 GB (OS+Flask+Redis ≈2, Ollama 7–8B ≈5.5, TTS ≈1,
OpenMontage render ≈8). See [DEPLOY.md](DEPLOY.md).

## 🧱 Stack & credits (projects we build on)

| Layer | Project | Link |
|---|---|---|
| Render engine | **OpenMontage** (this monorepo) | local |
| Composition runtime | **HyperFrames** | https://github.com/heygen-com/hyperframes |
| Composition runtime | **Remotion** | https://www.remotion.dev |
| Animation | **GSAP** | https://gsap.com |
| Web framework | **Flask** | https://flask.palletsprojects.com |
| ORM | **SQLAlchemy** | https://www.sqlalchemy.org |
| Admin UI | **Flask-Admin** | https://flask-admin.readthedocs.io |
| Task queue | **Celery** | https://docs.celeryq.dev |
| Broker | **Redis** | https://redis.io |
| Telegram | **aiogram** | https://docs.aiogram.dev |
| LLM runtime | **Ollama** (model: `qwen2.5:3b-instruct`) | https://ollama.com |
| TTS | **Kokoro-FastAPI** | https://github.com/remsky/Kokoro-FastAPI |
| TTS | **Piper** | https://github.com/rhasspy/piper |
| TTS (fallback) | **OpenAI** | https://github.com/openai/openai-python |
| Media | **FFmpeg** | https://ffmpeg.org |
| WSGI server | **Gunicorn** | https://gunicorn.org |

## 🤖 User flow (Telegram)

1. `/start` → intro: what it is, `500 ₽ / 5 videos`, current balance.
2. (optional) choose a **project** and **media source** (user / stock / mix), attach photos/videos.
3. Send a text prompt → 1 credit is charged → job enqueued.
4. Bot returns **storyboard + narration draft** with the inline buttons.
5. `Amend` → send edits (free) → the loop repeats.
6. `Approve` → final render enqueued → status messages, then the video is delivered.

## 🔌 External API (OpenAI-compatible)

```bash
curl https://api.YOURDOMAIN/v1/chat/completions \
  -H "Authorization: Bearer <API_KEY>" -H "Content-Type: application/json" \
  -d '{"model":"<LLM_MODEL>","messages":[{"role":"user","content":"привет"}]}'

curl https://api.YOURDOMAIN/v1/audio/speech \
  -H "Authorization: Bearer <API_KEY>" -H "Content-Type: application/json" \
  -d '{"input":"Бизнес-пад — это ERP.","gender":"female","response_format":"mp3"}' --output out.mp3
```

## 🚀 Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env         # fill SECRET_KEY, ADMIN_PASSWORD, OPENMONTAGE_DIR, LLM_MODEL, links…
.venv/bin/python -m scripts.init_db
./scripts/run_web.sh         # admin at http://127.0.0.1:8000/admin/
./scripts/run_worker.sh      # single-threaded render queue
./scripts/run_bots.sh        # after adding a bot token in the admin panel
```

Local dev without Redis: set `CELERY_TASK_ALWAYS_EAGER=1`. Full server setup (Ollama, TTS, systemd,
nginx/TLS): **[DEPLOY.md](DEPLOY.md)**.

## 📁 Layout

```
videobot/
  config.py  wsgi.py
  app/    models · admin · api · billing · llm · tts · render · celery_app · tasks
  bots/   runner · handlers · keyboards · texts · notify
  scripts/ init_db · run_*.sh      systemd/ web·worker·bots      docs/ landing page
```

## 📄 License

MIT. Branding (`videos.ai3d.art`) and the paid contact belong to the project owner.

---
Made for **videos.ai3d.art** · author **Vasily Kiselev**.
