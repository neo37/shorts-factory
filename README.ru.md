# VideoBot Platform

**Языки:** [English](README.md) · **Русский** · [Српски](README.sr.md)
**Лендинг:** https://videos.ai3d.art · **Доступ / пополнение:** [@kiselev_vasilli_andreevichd](https://t.me/kiselev_vasilli_andreevichd)

Мультибот-**SaaS-платформа**, которая превращает текстовый промт в брендированный вертикальный
**Shorts** (9:16). Пользователь общается с Telegram-ботом, получает **раскадровку + черновик
озвучки**, дорабатывает их в цикле, а после утверждения платформа рендерит готовое видео в
фиксированном стиле — на базе **OpenMontage** (HyperFrames/GSAP) для сборки, **LLM**
(через Ollama) для сценария и подключаемого движка **TTS** для озвучки. Также поднимается
**OpenAI-совместимый API**, чтобы внешние проекты переиспользовали ту же LLM и TTS.

> Один бот = один стиль. Рендеринг строго однопоточный, чтобы не перегружать CPU.

---

## ✨ Возможности

- **Промт → Shorts.** Свободный промт → структурированная раскадровка, субтитры и черновик озвучки.
- **Цикл правок.** Кнопки: `✅ Утвердить · ✏️ Дополнить · ❌ Отказаться · 🎬 Примеры · 💳 Пополнить`.
  Правки бесплатны; кредит списывается только при первом промте.
- **Загрузка медиа.** Фото и видео (≤ 20 МБ — лимит `getFile` Telegram Bot API) идут фоном сцен.
  Источник медиа: **свои / внешние стоки / микс**, с группировкой по **проектам**.
- **Мультибот.** Много токенов; каждый бот привязан к одному `design_style`.
- **Биллинг (кредиты).** Новым — 100 кредитов; 1 видео = 1 кредит. `500 ₽ = 5 видео` (ручное пополнение).
- **Несмываемый футер.** В каждом сообщении и видео — `https://videos.ai3d.art`.
- **Демо-watermark.** Показывается, пока админ не отметит пользователя оплаченным; футер остаётся всегда.
- **Админка** (Flask-Admin): боты, пользователи/биллинг, пресеты, задачи и **менеджер очереди Celery**
  (отменить задачу / сбросить всю очередь).
- **OpenAI-совместимый API** с авторизацией по ключу: `POST /v1/chat/completions`,
  `POST /v1/audio/speech` (мужской/женский голос, ударение `бизнес-пáд`), `GET /v1/models`.

## 🏗 Архитектура

```
Пользователи TG ─► aiogram-мультибот ─► Flask (биллинг, задачи) ─► Celery+Redis (concurrency=1)
                                          │                            │
                                   Панель Flask-Admin           1) LLM  → Ollama
                                          │                     2) TTS  → Kokoro / Piper / OpenAI
                                   SQLite (юзеры, боты,          3) Рендер → OpenMontage (HyperFrames)
                                   пресеты, задачи, ключи)             │
Внешние приложения ─► OpenAI-совместимый /v1 API ─────────────► футер videos.ai3d.art (постоянный)
```

Целевой сервер **8 vCPU / 24 ГБ RAM**; пик ≈16.5 ГБ (OS+Flask+Redis ≈2, Ollama 7–8B ≈5.5, TTS ≈1,
рендер OpenMontage ≈8). См. [DEPLOY.md](DEPLOY.md).

## 🧱 Стек и благодарности (проекты, на которых построено)

| Слой | Проект | Ссылка |
|---|---|---|
| Движок рендера | **OpenMontage** (этот монорепозиторий) | локально |
| Runtime сборки | **HyperFrames** | https://github.com/heygen-com/hyperframes |
| Runtime сборки | **Remotion** | https://www.remotion.dev |
| Анимация | **GSAP** | https://gsap.com |
| Веб-фреймворк | **Flask** | https://flask.palletsprojects.com |
| ORM | **SQLAlchemy** | https://www.sqlalchemy.org |
| Админка | **Flask-Admin** | https://flask-admin.readthedocs.io |
| Очередь задач | **Celery** | https://docs.celeryq.dev |
| Брокер | **Redis** | https://redis.io |
| Telegram | **aiogram** | https://docs.aiogram.dev |
| LLM-рантайм | **Ollama** (модель: `qwen2.5:3b-instruct`) | https://ollama.com |
| TTS | **Kokoro-FastAPI** | https://github.com/remsky/Kokoro-FastAPI |
| TTS | **Piper** | https://github.com/rhasspy/piper |
| TTS (fallback) | **OpenAI** | https://github.com/openai/openai-python |
| Медиа | **FFmpeg** | https://ffmpeg.org |
| WSGI-сервер | **Gunicorn** | https://gunicorn.org |

## 🤖 Сценарий (Telegram)

1. `/start` → интро: что это, `500 ₽ / 5 видео`, текущий баланс.
2. (опц.) выбрать **проект** и **источник медиа** (свои / стоки / микс), приложить фото/видео.
3. Отправить промт → списывается 1 кредит → задача в очередь.
4. Бот присылает **раскадровку + черновик озвучки** с инлайн-кнопками.
5. `Дополнить` → правки (бесплатно) → цикл повторяется.
6. `Утвердить` → финальный рендер в очередь → статусы, затем видео.

## 🔌 Внешний API (OpenAI-совместимый)

```bash
curl https://api.ВАШ_ДОМЕН/v1/chat/completions \
  -H "Authorization: Bearer <API_KEY>" -H "Content-Type: application/json" \
  -d '{"model":"<LLM_MODEL>","messages":[{"role":"user","content":"привет"}]}'

curl https://api.ВАШ_ДОМЕН/v1/audio/speech \
  -H "Authorization: Bearer <API_KEY>" -H "Content-Type: application/json" \
  -d '{"input":"Бизнес-пад — это ERP.","gender":"female","response_format":"mp3"}' --output out.mp3
```

## 🚀 Быстрый старт

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env         # заполнить SECRET_KEY, ADMIN_PASSWORD, OPENMONTAGE_DIR, LLM_MODEL, ссылки…
.venv/bin/python -m scripts.init_db
./scripts/run_web.sh         # админка на http://127.0.0.1:8000/admin/
./scripts/run_worker.sh      # однопоточная очередь рендера
./scripts/run_bots.sh        # после добавления токена бота в админке
```

Локально без Redis: `CELERY_TASK_ALWAYS_EAGER=1`. Полная установка на сервере (Ollama, TTS, systemd,
nginx/TLS): **[DEPLOY.md](DEPLOY.md)**.

## 📄 Лицензия

MIT. Брендинг (`videos.ai3d.art`) и платный контакт принадлежат владельцу проекта.

---
Сделано для **videos.ai3d.art** · автор **Василий Киселёв**.
