"""Flask-Admin panel: bots, users/billing, presets, api-keys, and a Celery queue manager."""
from functools import wraps

from flask import Response, redirect, request, url_for, flash
from flask_admin import Admin, AdminIndexView, BaseView, expose
from flask_admin.contrib.sqla import ModelView

from config import Config
from .models import db, User, Bot, Preset, Job, ApiKey, Project, ApiRequest


# ---------- HTTP basic auth gate ----------
def _check_auth(u, p):
    return u == Config.ADMIN_USER and p == Config.ADMIN_PASSWORD


def _authenticate():
    return Response("Auth required", 401, {"WWW-Authenticate": 'Basic realm="videobot-admin"'})


def requires_auth(f):
    @wraps(f)
    def wrapper(*a, **kw):
        auth = request.authorization
        if not auth or not _check_auth(auth.username, auth.password):
            return _authenticate()
        return f(*a, **kw)
    return wrapper


class AuthMixin:
    def is_accessible(self):
        auth = request.authorization
        return bool(auth and _check_auth(auth.username, auth.password))

    def inaccessible_callback(self, name, **kw):
        return _authenticate()


class SecureIndex(AuthMixin, AdminIndexView):
    pass


class SecureModelView(AuthMixin, ModelView):
    pass


class UserView(SecureModelView):
    column_list = ("telegram_id", "username", "first_name", "credits", "is_paid", "created_at")
    column_searchable_list = ("telegram_id", "username", "first_name")
    column_editable_list = ("credits", "is_paid")     # manual balance correction
    form_columns = ("telegram_id", "username", "first_name", "credits", "is_paid")


class BotView(SecureModelView):
    column_list = ("name", "token", "design_style", "is_active", "created_at")
    form_columns = ("name", "token", "design_style", "is_active")
    column_editable_list = ("design_style", "is_active")


class PresetView(SecureModelView):
    column_list = ("slug", "title", "example_render")
    form_columns = ("slug", "title", "description", "example_render")


class ApiKeyView(SecureModelView):
    column_list = ("name", "key", "is_active", "created_at")
    form_columns = ("name", "key", "is_active")
    can_edit = True


class ApiRequestView(SecureModelView):
    column_list = ("id", "contact", "items_json", "handled", "created_at")
    column_editable_list = ("handled",)
    column_default_sort = ("created_at", True)
    can_create = False


class JobView(SecureModelView):
    column_list = ("id", "bot_id", "telegram_id", "design_style", "media_source", "status", "created_at")
    column_filters = ("status", "design_style", "media_source", "bot_id")
    column_searchable_list = ("telegram_id", "prompt")
    can_create = False
    can_edit = True


class ProjectView(SecureModelView):
    column_list = ("id", "user_id", "name", "media_source", "created_at")
    column_filters = ("media_source",)
    form_columns = ("user_id", "name", "media_source")


class QueueView(AuthMixin, BaseView):
    """Celery task manager: cancel one task or purge the whole queue."""

    @expose("/")
    def index(self):
        active = Job.query.filter(Job.status.in_(("queued", "processing", "rendering"))).order_by(
            Job.id.desc()).all()
        recent = Job.query.order_by(Job.id.desc()).limit(50).all()
        return self.render("queue.html", active=active, recent=recent)

    @expose("/cancel/<int:job_id>")
    def cancel(self, job_id):
        job = db.session.get(Job, job_id)
        if job:
            try:
                from .celery_app import celery
                if job.celery_id:
                    celery.control.revoke(job.celery_id, terminate=True, signal="SIGTERM")
            except Exception as e:  # noqa: BLE001
                flash(f"revoke error: {e}", "error")
            job.status = "cancelled"
            db.session.commit()
            flash(f"job {job_id} cancelled")
        return redirect(url_for(".index"))

    @expose("/purge")
    def purge(self):
        try:
            from .celery_app import celery
            celery.control.purge()
            flash("queue purged (Redis)")
        except Exception as e:  # noqa: BLE001
            flash(f"purge error: {e}", "error")
        Job.query.filter(Job.status.in_(("queued", "processing"))).update(
            {Job.status: "cancelled"}, synchronize_session=False)
        db.session.commit()
        return redirect(url_for(".index"))


def init_admin(app):
    admin = Admin(app, name="VideoBot Admin", index_view=SecureIndex(url="/admin2"),
                  url="/admin2", template_mode="bootstrap4")
    admin.add_view(BotView(Bot, db.session, name="Боты"))
    admin.add_view(UserView(User, db.session, name="Пользователи"))
    admin.add_view(ProjectView(Project, db.session, name="Проекты"))
    admin.add_view(JobView(Job, db.session, name="Задачи"))
    admin.add_view(QueueView(name="Очередь", endpoint="queue"))
    admin.add_view(PresetView(Preset, db.session, name="Пресеты"))
    admin.add_view(ApiKeyView(ApiKey, db.session, name="API-ключи"))
    admin.add_view(ApiRequestView(ApiRequest, db.session, name="Заявки на API"))
    return admin
