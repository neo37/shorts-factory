"""Fetch and extract readable content from URLs found in a user's prompt.

Runs inside the worker (part of the heavy queue). Best-effort: network/parse failures
are swallowed so the storyboard still generates from the prompt alone.
"""
import logging
import re

import requests

log = logging.getLogger("videobot.webfetch")

URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_SCRIPT_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_DESC_RE = re.compile(
    r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]*'
    r'content=["\'](.*?)["\']', re.IGNORECASE)

MAX_URLS = 3
PER_PAGE_CHARS = 1500


def extract_urls(text):
    if not text:
        return []
    seen, out = set(), []
    for m in URL_RE.findall(text):
        u = m.rstrip(".,);")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:MAX_URLS]


def _fetch_one(url):
    r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 VideoBot"})
    r.raise_for_status()
    html = r.text
    title = ""
    mt = _TITLE_RE.search(html)
    if mt:
        title = _WS_RE.sub(" ", _TAG_RE.sub("", mt.group(1))).strip()
    desc = ""
    md = _DESC_RE.search(html)
    if md:
        desc = _WS_RE.sub(" ", md.group(1)).strip()
    body = _SCRIPT_RE.sub(" ", html)
    body = _TAG_RE.sub(" ", body)
    body = _WS_RE.sub(" ", body).strip()
    parts = [p for p in (title, desc, body) if p]
    text = " — ".join(parts)
    return text[:PER_PAGE_CHARS]


_HEX_RE = re.compile(r"#([0-9a-fA-F]{6})\b")


def _luma(hex6):
    r, g, b = int(hex6[0:2], 16), int(hex6[2:4], 16), int(hex6[4:6], 16)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _sat(hex6):
    r, g, b = [int(hex6[i:i+2], 16) for i in (0, 2, 4)]
    mx, mn = max(r, g, b), min(r, g, b)
    return (mx - mn) / 255.0


def extract_theme(url):
    """Fetch a page and derive a theme dict (bg/panel/primary/accent/fg…) from its colors.
    Returns None on failure. Font stays a safe default."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 VideoBot"})
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        log.warning("theme fetch failed for %s: %s", url, e)
        return None
    hexes = [h.lower() for h in _HEX_RE.findall(r.text)]
    if len(hexes) < 3:
        return None
    # frequency
    freq = {}
    for h in hexes:
        freq[h] = freq.get(h, 0) + 1
    ranked = sorted(freq, key=lambda h: -freq[h])
    # background = most frequent; decide dark/light by its luma
    bg = ranked[0]
    dark = _luma(bg) < 128
    fg = "#FFFFFF" if dark else "#141414"
    # accent colors = most saturated among frequent
    vivid = sorted((h for h in ranked[:20]), key=lambda h: -_sat(h))
    vivid = [h for h in vivid if _sat(h) > 0.25] or ranked[1:3]
    primary = "#" + vivid[0].upper()
    accent = "#" + (vivid[1] if len(vivid) > 1 else vivid[0]).upper()
    panel = "#1A1A1A" if dark else "#F5F5F7"
    return {
        "label": "from-url",
        "bg": "#" + bg.upper(), "panel": panel, "primary": primary, "accent": accent,
        "fg": fg, "fg2": ("rgba(255,255,255,.72)" if dark else "#424245"),
        "muted": ("rgba(255,255,255,.5)" if dark else "#86868B"),
        "font_family": '"Manrope",system-ui,sans-serif',
        "font_url": "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap",
        "radius": 20, "border": "none", "shadow": "0 8px 40px rgba(0,0,0,.18)",
        "scrim": ("rgba(0,0,0,.5)" if dark else "rgba(0,0,0,.35)"),
        "h1_weight": 800, "eyebrow_upper": True,
    }


def fetch_context(text):
    """Return a context string built from any URLs in `text`, or '' if none/failed."""
    urls = extract_urls(text)
    if not urls:
        return ""
    chunks = []
    for u in urls:
        try:
            content = _fetch_one(u)
            if content:
                chunks.append(f"[{u}]\n{content}")
                log.info("fetched %d chars from %s", len(content), u)
        except Exception as e:  # noqa: BLE001
            log.warning("fetch failed for %s: %s", u, e)
    if not chunks:
        return ""
    return "Контент со страниц по ссылкам (используй как фактуру для сценария):\n" + "\n\n".join(chunks)
