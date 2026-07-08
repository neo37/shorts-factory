"""Public site: landing page at /, OpenAPI spec, and the 'request API keys' lead form."""
import json
import logging

from flask import Blueprint, jsonify, render_template, request

from config import Config
from .models import db, ApiRequest

log = logging.getLogger("videobot.site")
site_bp = Blueprint("site", __name__)


@site_bp.get("/")
def landing():
    return render_template("landing.html",
                           footer_url=Config.PROJECT_FOOTER_URL,
                           topup_url=Config.TOPUP_CONTACT_URL)


@site_bp.post("/request-keys")
def request_keys():
    data = request.get_json(silent=True) or request.form
    contact = (data.get("contact") or "").strip()
    if not contact:
        return jsonify({"ok": False, "error": "Укажите контакт."}), 400
    items = data.get("items")
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except ValueError:
            items = [items]
    lead = ApiRequest(contact=contact[:256],
                      items_json=json.dumps(items, ensure_ascii=False) if items else None,
                      note=(data.get("note") or "")[:2000])
    db.session.add(lead)
    db.session.commit()
    log.info("API key request from %s (items=%s)", contact, items)
    return jsonify({"ok": True})


@site_bp.get("/openapi.json")
def openapi():
    base = Config.PUBLIC_BASE_URL.rstrip("/")
    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "VideoBot API (OpenAI-compatible)",
            "version": "1.0.0",
            "description": (
                "OpenAI-compatible API: LLM chat, text-to-speech and speech-to-text. "
                "Authenticate with `Authorization: Bearer <API_KEY>`. "
                "Request a key via the form on the landing page."
            ),
        },
        "servers": [{"url": base}],
        "security": [{"bearerAuth": []}],
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer"}
            }
        },
        "paths": {
            "/v1/chat/completions": {
                "post": {
                    "summary": "Chat completions (proxied to the LLM)",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "model": {"type": "string", "example": Config.LLM_MODEL},
                            "messages": {"type": "array", "items": {"type": "object"}},
                            "stream": {"type": "boolean"},
                        }, "required": ["messages"]}}}},
                    "responses": {"200": {"description": "OpenAI-shaped chat completion"}},
                }
            },
            "/v1/audio/speech": {
                "post": {
                    "summary": "Text-to-speech (male/female voices)",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "input": {"type": "string", "example": "Бизнес-пад — это ERP."},
                            "voice": {"type": "string", "example": "nova"},
                            "gender": {"type": "string", "enum": ["female", "male", "neutral"]},
                            "response_format": {"type": "string", "enum": ["mp3", "wav"], "default": "mp3"},
                        }, "required": ["input"]}}}},
                    "responses": {"200": {"description": "Audio file", "content": {"audio/mpeg": {}}}},
                }
            },
            "/v1/audio/transcriptions": {
                "post": {
                    "summary": "Speech-to-text (queued ASR)",
                    "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
                        "type": "object",
                        "properties": {"file": {"type": "string", "format": "binary"}},
                        "required": ["file"]}}}},
                    "responses": {"200": {"description": "{\"text\": \"...\"}"}},
                }
            },
            "/v1/models": {
                "get": {"summary": "List available models",
                        "responses": {"200": {"description": "OpenAI-shaped model list"}}}
            },
        },
    }
    return jsonify(spec)
