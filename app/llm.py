"""LLM access via Ollama (OpenAI-compatible).

Produces a structured storyboard + draft narration from a free-form user prompt.
Falls back to a deterministic template if Ollama is unreachable (keeps local dev working).
"""
import json
import logging

from openai import OpenAI
from config import Config

log = logging.getLogger("videobot.llm")

SYSTEM_PROMPT = (
    "Ты — сценарист коротких вертикальных видео (Shorts, 9:16, ~50-60 сек). "
    "По запросу пользователя верни СТРОГО JSON без markdown, по схеме:\n"
    "{\n"
    '  "title": "краткий заголовок",\n'
    '  "hook": "цепляющая фраза для первой сцены",\n'
    '  "scenes": [ {"eyebrow": "надпись сверху", "headline": "крупный текст", '
    '"caption": "субтитр 1 строкой", "vo": "текст озвучки для сцены"} ],\n'
    '  "outro": {"headline": "финальная фраза", "cta": "призыв"},\n'
    '  "vo_full": "цельный текст озвучки на весь ролик"\n'
    "}\n"
    "Правила: 4-6 сцен; коротко и энергично; на русском; никаких пояснений вне JSON."
)


def _client():
    return OpenAI(base_url=Config.OLLAMA_BASE_URL, api_key=Config.OLLAMA_API_KEY,
                  timeout=Config.LLM_TIMEOUT)


def _fallback_storyboard(prompt, corrections=""):
    """Deterministic offline storyboard so the pipeline works without Ollama."""
    topic = prompt.strip() or "новый продукт"
    scenes = [
        {"eyebrow": "shorts", "headline": topic[:40],
         "caption": f"Разбираем: {topic[:60]}", "vo": f"Сегодня коротко о главном: {topic}."},
        {"eyebrow": "суть", "headline": "Что это даёт",
         "caption": "Главная польза за 10 секунд", "vo": "Вот что это меняет на практике."},
        {"eyebrow": "как", "headline": "Как это работает",
         "caption": "Простыми словами", "vo": "Работает это так — быстро и понятно."},
    ]
    if corrections:
        scenes.append({"eyebrow": "правки", "headline": "С учётом правок",
                       "caption": corrections[:60], "vo": corrections})
    vo_full = " ".join(s["vo"] for s in scenes)
    return {
        "title": topic[:60],
        "hook": f"{topic} — коротко и по делу.",
        "scenes": scenes,
        "outro": {"headline": "Подписывайся", "cta": "Ссылки в описании"},
        "vo_full": vo_full,
        "_offline": True,
    }


def generate_storyboard(prompt, corrections="", model=None):
    """Return (storyboard_dict, vo_draft_text). Never raises — falls back offline.
    If the prompt contains URLs, their page content is fetched and added as context."""
    user_msg = prompt if not corrections else f"{prompt}\n\nПравки пользователя: {corrections}"
    try:
        from . import webfetch
        ctx = webfetch.fetch_context(f"{prompt}\n{corrections}")
        if ctx:
            user_msg = f"{user_msg}\n\n{ctx}"
    except Exception as e:  # noqa: BLE001
        log.warning("web context skipped: %s", e)
    try:
        client = _client()
        resp = client.chat.completions.create(
            model=model or Config.LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        data = json.loads(raw)
        vo = data.get("vo_full") or " ".join(s.get("vo", "") for s in data.get("scenes", []))
        return data, vo
    except Exception as e:  # noqa: BLE001 — offline/dev resilience is intentional
        log.warning("LLM unavailable (%s); using offline storyboard", e)
        data = _fallback_storyboard(prompt, corrections)
        return data, data["vo_full"]
