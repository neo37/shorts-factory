# VideoBot Platform

**Jezici:** [English](README.md) · [Русский](README.ru.md) · **Srpski**
**Landing:** https://videos.ai3d.art · **Pristup / dopuna:** [@kiselev_vasilli_andreevichd](https://t.me/kiselev_vasilli_andreevichd)

Multi-bot **SaaS platforma** koja od tekstualnog prompta pravi brendiran vertikalni **Short** (9:16).
Korisnik ćaska sa Telegram botom, dobija **storyboard + nacrt naracije**, dorađuje ih u petlji, a
nakon odobrenja platforma renderuje gotov video u fiksnom stilu — na osnovu **OpenMontage**
(HyperFrames/GSAP) za kompoziciju, **LLM-a** (preko Ollama) za scenario i priključivog
**TTS** motora za naraciju. Takođe pruža **API kompatibilan sa OpenAI** da spoljni projekti koriste
isti LLM i TTS.

> Jedan bot = jedan stil dizajna. Renderovanje je strogo jednonitno da ne preoptereti CPU.

---

## ✨ Mogućnosti

- **Prompt → Short.** Slobodan prompt → strukturiran storyboard, titlovi scena i nacrt naracije.
- **Petlja doradе.** Dugmad: `✅ Odobri · ✏️ Dopuni · ❌ Odustani · 🎬 Primeri · 💳 Dopuna`.
  Izmene su besplatne; kredit se naplaćuje samo pri prvom promptu.
- **Otpremanje medija.** Fotografije i video (≤ 20 MB — limit `getFile` Telegram Bot API-ja) postaju
  pozadine scena. Izvor medija: **korisnički / eksterni stock / miks**, grupisano po **projektima**.
- **Multi-bot.** Više tokena; svaki bot je vezan za jedan `design_style`.
- **Naplata (krediti).** Novi korisnici dobijaju 100 kredita; 1 video = 1 kredit. `500 ₽ = 5 videa`.
- **Neizbrisiv potpis.** Svaka poruka i video nose `https://videos.ai3d.art`.
- **Demo watermark.** Prikazuje se dok admin ne označi korisnika kao plaćenog; potpis ostaje uvek.
- **Admin panel** (Flask-Admin): botovi, korisnici/naplata, preseti, zadaci i **Celery menadžer reda**
  (otkaži zadatak / isprazni ceo red).
- **API kompatibilan sa OpenAI** uz autorizaciju po ključu: `POST /v1/chat/completions`,
  `POST /v1/audio/speech` (muški/ženski glas, akcenat `бизнес-пáд`), `GET /v1/models`.

## 🏗 Arhitektura

```
Telegram korisnici ─► aiogram multibot ─► Flask (naplata, zadaci) ─► Celery+Redis (concurrency=1)
                                            │                            │
                                     Flask-Admin panel            1) LLM  → Ollama
                                            │                      2) TTS  → Kokoro / Piper / OpenAI
                                     SQLite (korisnici, botovi,    3) Render → OpenMontage (HyperFrames)
                                     preseti, zadaci, ključevi)          │
Spoljne aplikacije ─► OpenAI-kompatibilan /v1 API ────────────► potpis videos.ai3d.art (trajni)
```

Ciljni server **8 vCPU / 24 GB RAM**; vrh ≈16.5 GB (OS+Flask+Redis ≈2, Ollama 7–8B ≈5.5, TTS ≈1,
render OpenMontage ≈8). Vidi [DEPLOY.md](DEPLOY.md).

## 🧱 Stack i zahvalnice (projekti na kojima počiva)

| Sloj | Projekat | Link |
|---|---|---|
| Render motor | **OpenMontage** (ovaj monorepo) | lokalno |
| Kompozicija | **HyperFrames** | https://github.com/heygen-com/hyperframes |
| Kompozicija | **Remotion** | https://www.remotion.dev |
| Animacija | **GSAP** | https://gsap.com |
| Web framework | **Flask** | https://flask.palletsprojects.com |
| ORM | **SQLAlchemy** | https://www.sqlalchemy.org |
| Admin UI | **Flask-Admin** | https://flask-admin.readthedocs.io |
| Red zadataka | **Celery** | https://docs.celeryq.dev |
| Broker | **Redis** | https://redis.io |
| Telegram | **aiogram** | https://docs.aiogram.dev |
| LLM runtime | **Ollama** (model: `qwen2.5:3b-instruct`) | https://ollama.com |
| TTS | **Kokoro-FastAPI** | https://github.com/remsky/Kokoro-FastAPI |
| TTS | **Piper** | https://github.com/rhasspy/piper |
| TTS (fallback) | **OpenAI** | https://github.com/openai/openai-python |
| Mediji | **FFmpeg** | https://ffmpeg.org |
| WSGI server | **Gunicorn** | https://gunicorn.org |

## 🤖 Tok korišćenja (Telegram)

1. `/start` → intro: šta je to, `500 ₽ / 5 videa`, trenutni saldo.
2. (opciono) izaberi **projekat** i **izvor medija** (svoj / stock / miks), priloži foto/video.
3. Pošalji tekstualni prompt → naplaćuje se 1 kredit → zadatak ide u red.
4. Bot vraća **storyboard + nacrt naracije** sa inline dugmadima.
5. `Dopuni` → pošalji izmene (besplatno) → petlja se ponavlja.
6. `Odobri` → finalni render u redu → statusi, zatim isporuka videa.

## 🔌 Spoljni API (OpenAI-kompatibilan)

```bash
curl https://api.VAS_DOMEN/v1/chat/completions \
  -H "Authorization: Bearer <API_KEY>" -H "Content-Type: application/json" \
  -d '{"model":"<LLM_MODEL>","messages":[{"role":"user","content":"zdravo"}]}'

curl https://api.VAS_DOMEN/v1/audio/speech \
  -H "Authorization: Bearer <API_KEY>" -H "Content-Type: application/json" \
  -d '{"input":"Бизнес-пад је ERP.","gender":"female","response_format":"mp3"}' --output out.mp3
```

## 🚀 Brzi start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env         # popuni SECRET_KEY, ADMIN_PASSWORD, OPENMONTAGE_DIR, LLM_MODEL, linkove…
.venv/bin/python -m scripts.init_db
./scripts/run_web.sh         # admin na http://127.0.0.1:8000/admin/
./scripts/run_worker.sh      # jednonitni red za render
./scripts/run_bots.sh        # nakon dodavanja tokena bota u admin panelu
```

Lokalno bez Redis-a: `CELERY_TASK_ALWAYS_EAGER=1`. Potpuna serverska instalacija (Ollama, TTS, systemd,
nginx/TLS): **[DEPLOY.md](DEPLOY.md)**.

## 📄 Licenca

MIT. Brendiranje (`videos.ai3d.art`) i plaćeni kontakt pripadaju vlasniku projekta.

---
Napravljeno za **videos.ai3d.art** · autor **Vasilij Kiseljov**.
