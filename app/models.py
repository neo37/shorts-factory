"""SQLAlchemy models: users, bots, design presets, jobs (queue), external API keys."""
import secrets
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _now():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, index=True, nullable=False)
    username = db.Column(db.String(128))
    first_name = db.Column(db.String(128))
    credits = db.Column(db.Integer, default=0, nullable=False)
    # is_paid removes the demo watermark; the videos.ai3d.art footer is ALWAYS kept.
    is_paid = db.Column(db.Boolean, default=False, nullable=False)
    active_project_id = db.Column(db.Integer)   # currently selected Project
    created_at = db.Column(db.DateTime, default=_now)

    def __repr__(self):
        return f"<User tg={self.telegram_id} credits={self.credits}>"


class Bot(db.Model):
    __tablename__ = "bots"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    token = db.Column(db.String(128), unique=True, nullable=False)
    # One bot = one fixed design style (preset id / slug in OpenMontage).
    design_style = db.Column(db.String(64), nullable=False, default="businesspad-dark")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    def __repr__(self):
        return f"<Bot {self.name} style={self.design_style}>"


class Preset(db.Model):
    """Design-style preset metadata (maps to an OpenMontage template)."""
    __tablename__ = "presets"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False)
    title = db.Column(db.String(128))
    description = db.Column(db.Text)
    # Path (relative to OpenMontage) to an example render shown via "Смотреть примеры".
    example_render = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=_now)

    def __repr__(self):
        return f"<Preset {self.slug}>"


class Project(db.Model):
    """A user workspace: groups uploaded media and jobs. Holds the media-source choice."""
    __tablename__ = "projects"
    MEDIA_SOURCES = ("user", "stock", "mix")  # own media / external stock / mix

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    name = db.Column(db.String(128), default="Мой проект")
    media_source = db.Column(db.String(16), default="mix")
    media_json = db.Column(db.Text)            # JSON list of media staged for this project
    created_at = db.Column(db.DateTime, default=_now)

    def __repr__(self):
        return f"<Project {self.name} src={self.media_source}>"


class Job(db.Model):
    __tablename__ = "jobs"
    STATUS = ("queued", "transcribing", "processing", "awaiting_user",
              "rendering", "done", "error", "cancelled")

    id = db.Column(db.Integer, primary_key=True)
    celery_id = db.Column(db.String(64), index=True)
    bot_id = db.Column(db.Integer, db.ForeignKey("bots.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"))
    telegram_id = db.Column(db.BigInteger, index=True)
    chat_id = db.Column(db.BigInteger)

    design_style = db.Column(db.String(64))
    media_source = db.Column(db.String(16), default="mix")
    voice_path = db.Column(db.String(256))     # staged voice message awaiting transcription
    prompt = db.Column(db.Text)                # latest effective prompt (prompt + corrections)
    corrections = db.Column(db.Text)           # accumulated correction notes
    storyboard_json = db.Column(db.Text)       # structured storyboard from LLM
    vo_draft = db.Column(db.Text)              # draft narration text
    media_json = db.Column(db.Text)            # JSON list of user-uploaded media file paths
    watermark = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(16), default="queued", index=True)
    error = db.Column(db.Text)
    output_path = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    bot = db.relationship("Bot", backref="jobs")
    user = db.relationship("User", backref="jobs")

    def __repr__(self):
        return f"<Job {self.id} {self.status}>"


class UploadToken(db.Model):
    """One-off web upload link for media too large for Telegram's bot limit."""
    __tablename__ = "upload_tokens"
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(48), unique=True, index=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"))
    telegram_id = db.Column(db.BigInteger)
    uploaded = db.Column(db.Integer, default=0)     # files uploaded via this link
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=_now)

    @staticmethod
    def generate(user, project, ttl_hours):
        from datetime import timedelta
        return UploadToken(
            token=secrets.token_urlsafe(24), user_id=user.id, project_id=project.id,
            telegram_id=user.telegram_id, expires_at=_now() + timedelta(hours=ttl_hours),
        )

    def is_valid(self):
        exp = self.expires_at
        if exp is None:
            return True
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return _now() <= exp


class ApiRequest(db.Model):
    """A lead from the landing 'request API keys' form."""
    __tablename__ = "api_requests"
    id = db.Column(db.Integer, primary_key=True)
    contact = db.Column(db.String(256), nullable=False)   # required
    items_json = db.Column(db.Text)                       # selected services/models
    note = db.Column(db.Text)
    handled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=_now)

    def __repr__(self):
        return f"<ApiRequest {self.contact}>"


class ApiKey(db.Model):
    """External API key for OpenAI-compatible /v1 endpoints."""
    __tablename__ = "api_keys"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    key = db.Column(db.String(72), unique=True, index=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    @staticmethod
    def generate(name="external"):
        return ApiKey(name=name, key="vbp-" + secrets.token_urlsafe(36))

    def __repr__(self):
        return f"<ApiKey {self.name} active={self.is_active}>"
