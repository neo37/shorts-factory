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
