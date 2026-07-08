# VideoBot Platform — Deployment (alongside OpenMontage)

Multibot SaaS: Flask + SQLAlchemy + Flask-Admin, Celery+Redis queue, aiogram multibot,
uncensored LLM via Ollama (OpenAI-compatible) and a TTS engine, plus an external
OpenAI-compatible API. Rendering runs through OpenMontage (HyperFrames) **single-threaded**.

Target host: **8 vCPU / 24 GB RAM**. Peak RAM budget (TZ §4): OS+Flask+Redis ≈2 GB,
Ollama 7–8B ≈5.5 GB, TTS ≈1 GB, OpenMontage render peak ≈8 GB → ~16.5 GB, ~7.5 GB headroom.

---

## 0. Layout

Deployed **together with OpenMontage**. Expected paths:

```
/home/n36/VIDEO/OpenMontage          # the render engine (this repo)
/home/n36/VIDEO/OpenMontage/videobot # this platform (self-contained, own venv)
```

`OPENMONTAGE_DIR` in `.env` points the render step at the engine. Generated bot videos land in
`OpenMontage/projects/bot-<jobid>/hyperframes/renders/final.mp4`.

---

## 1. System dependencies

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip redis-server ffmpeg curl git
# Node.js >= 22 for HyperFrames (if not already present for OpenMontage)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node --version   # v22+

sudo systemctl enable --now redis-server
```

## 2. Ollama + uncensored model (OpenAI-compatible LLM)

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama

# Pull an uncensored (abliterated) instruct model in GGUF, ~5–6 GB:
ollama pull huihui_ai/qwen2.5-abliterate:7b
#   alternatives: dolphin-mistral, huihui_ai/llama3.1-abliterate, mistral-nemo uncensored, etc.
```

Ollama already exposes an OpenAI-compatible API at `http://localhost:11434/v1`.
Set `LLM_MODEL` in `.env` to the exact tag you pulled.

## 3. TTS engine (choose one; `TTS_BACKEND=auto` tries kokoro → piper → openai)

**Kokoro-FastAPI (recommended, OpenAI-compatible /v1/audio/speech):**
```bash
docker run -d --name kokoro -p 8880:8880 ghcr.io/remsky/kokoro-fastapi:latest
# -> KOKORO_BASE_URL=http://localhost:8880/v1
```

**or Piper (lightweight, local binary):**
```bash
# install piper + download ru voices, then set PIPER_BIN / PIPER_VOICE_* in .env
```

**or OpenAI fallback:** set `OPENAI_API_KEY` in `.env`.

## 4. Platform install

```bash
cd /home/n36/VIDEO/OpenMontage/videobot
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# edit .env: SECRET_KEY, ADMIN_PASSWORD, OPENMONTAGE_DIR, LLM_MODEL, TTS_BACKEND, links…

.venv/bin/python -m scripts.init_db   # creates tables, seeds presets, prints an API key
```

## 5. Run (dev)

```bash
# Terminal 1 — web + admin + API
./scripts/run_web.sh                      # http://127.0.0.1:8000/admin/

# Terminal 2 — queue worker (single-threaded)
./scripts/run_worker.sh

# Terminal 3 — telegram bots (after adding a token in admin → Боты)
./scripts/run_bots.sh
```

Local dev without Redis: set `CELERY_TASK_ALWAYS_EAGER=1` in `.env` (tasks run inline).

## 6. Run (production, systemd)

```bash
sudo cp systemd/videobot-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now videobot-web videobot-worker videobot-bots
sudo systemctl status videobot-worker
journalctl -u videobot-bots -f
```

## 7. Domain + HTTPS (nginx) — for the external OpenAI-compatible API

When you have the domain, expose only the API/admin behind TLS:

```nginx
server {
    server_name api.YOURDOMAIN;
    location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; }
}
```
```bash
sudo certbot --nginx -d api.YOURDOMAIN
```

External clients then use it exactly like OpenAI:
```bash
curl https://api.YOURDOMAIN/v1/chat/completions \
  -H "Authorization: Bearer <API_KEY_from_init_db>" \
  -H "Content-Type: application/json" \
  -d '{"model":"'"$LLM_MODEL"'","messages":[{"role":"user","content":"привет"}]}'

curl https://api.YOURDOMAIN/v1/audio/speech \
  -H "Authorization: Bearer <API_KEY>" -H "Content-Type: application/json" \
  -d '{"input":"Бизнес-пад — это ERP.","gender":"female","response_format":"mp3"}' --output out.mp3
```

## 8. Admin panel

`http://127.0.0.1:8000/admin/` (HTTP basic: `ADMIN_USER`/`ADMIN_PASSWORD`).

- **Боты** — add Telegram tokens, set `design_style` per bot (one bot = one style). Restart `videobot-bots` after changes.
- **Пользователи** — edit `credits` (manual top-up after payment), toggle `is_paid` to remove the demo watermark.
- **Задачи / Очередь** — see statuses; **Отменить** (Celery revoke) / **Сбросить всю очередь** (Redis purge).
- **API-ключи** — generate keys for external LLM/TTS consumers.

## 9. Notes / guarantees

- The `videos.ai3d.art` footer is appended to every bot message and burned into every rendered
  video — it is **not removable**.
- The demo watermark (top of video) is shown while `user.is_paid = false`; set the flag after payment.
- New users get `NEW_USER_CREDITS` (default 100). 1 credit = 1 video; corrections are free.
- Payment is manual via `TOPUP_CONTACT_URL` (t.me/kiselev_vasilli_andreevichd); adjust balance in admin.
