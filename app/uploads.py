"""Web upload for media too large for Telegram's ~20 MB bot limit.

The bot mints a one-off UploadToken and sends the user a link. The page below lets them
upload big photos/videos straight to Flask (up to MAX_WEB_UPLOAD_MB), attaches them to the
token's Project, and shows live status.
"""
import logging
import uuid
from pathlib import Path

from flask import Blueprint, abort, jsonify, render_template, request

from config import Config
from .models import db, UploadToken, Project
from . import billing

log = logging.getLogger("videobot.uploads")
uploads_bp = Blueprint("uploads", __name__)

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
_VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v", ".avi", ".mkv"}


def _load(token):
    row = UploadToken.query.filter_by(token=token).first()
    if not row or not row.is_valid():
        return None
    return row


@uploads_bp.get("/upload/<token>")
def upload_form(token):
    row = _load(token)
    if not row:
        return render_template("upload.html", invalid=True, token=token,
                               project_name="", uploaded=0, max_mb=Config.MAX_WEB_UPLOAD_MB), 404
    proj = db.session.get(Project, row.project_id)
    return render_template(
        "upload.html", invalid=False, token=token,
        project_name=(proj.name if proj else "проект"),
        uploaded=row.uploaded or 0, max_mb=Config.MAX_WEB_UPLOAD_MB,
    )


@uploads_bp.get("/upload/<token>/status")
def upload_status(token):
    row = _load(token)
    if not row:
        return jsonify({"valid": False}), 404
    proj = db.session.get(Project, row.project_id)
    return jsonify({
        "valid": True,
        "project": proj.name if proj else None,
        "uploaded": row.uploaded or 0,
        "media_count": len(billing.project_media(proj)) if proj else 0,
    })


@uploads_bp.post("/upload/<token>")
def upload_receive(token):
    row = _load(token)
    if not row:
        return jsonify({"ok": False, "error": "Ссылка недействительна или истекла."}), 404
    proj = db.session.get(Project, row.project_id)
    if not proj:
        return jsonify({"ok": False, "error": "Проект не найден."}), 404

    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "Файл не выбран."}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in _IMAGE_EXT and ext not in _VIDEO_EXT:
        return jsonify({"ok": False, "error": "Только фото или видео."}), 400

    dest_dir = Config.DATA_DIR / "media" / str(row.telegram_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    # normalize extension for the renderer (images -> .jpg tag handled downstream)
    save_ext = ".mp4" if ext in _VIDEO_EXT else ".jpg"
    dest = dest_dir / f"{uuid.uuid4().hex}{save_ext}"
    f.save(str(dest))

    count = billing.add_project_media(proj, str(dest))
    row.uploaded = (row.uploaded or 0) + 1
    db.session.commit()
    log.info("web upload token=%s -> %s (project media=%d)", token, dest.name, count)
    return jsonify({"ok": True, "uploaded": row.uploaded, "media_count": count,
                    "filename": f.filename})
