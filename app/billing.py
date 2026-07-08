"""Credit/billing helpers. One video = CREDITS_PER_VIDEO. New users get NEW_USER_CREDITS."""
import json

from config import Config
from .models import db, User, Project


def get_or_create_user(telegram_id, username=None, first_name=None):
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            credits=Config.NEW_USER_CREDITS,
            is_paid=False,
        )
        db.session.add(user)
        db.session.commit()
    else:
        # keep profile fresh
        changed = False
        if username and user.username != username:
            user.username, changed = username, True
        if first_name and user.first_name != first_name:
            user.first_name, changed = first_name, True
        if changed:
            db.session.commit()
    return user


def has_credit(user):
    return user.credits >= Config.CREDITS_PER_VIDEO


def charge(user):
    """Deduct one video's worth of credits. Returns True if charged."""
    if not has_credit(user):
        return False
    user.credits -= Config.CREDITS_PER_VIDEO
    db.session.commit()
    return True


def refund(user):
    user.credits += Config.CREDITS_PER_VIDEO
    db.session.commit()


def watermark_for(user):
    """Demo watermark shown unless the user has paid. Footer link is always kept."""
    return not user.is_paid


# ---------- projects ----------
def get_active_project(user):
    """Return the user's active Project, creating a default one if none exists."""
    proj = None
    if user.active_project_id:
        proj = db.session.get(Project, user.active_project_id)
    if proj is None:
        proj = Project.query.filter_by(user_id=user.id).first()
    if proj is None:
        proj = Project(user_id=user.id, name="Мой проект", media_source="mix")
        db.session.add(proj)
        db.session.commit()
        user.active_project_id = proj.id
        db.session.commit()
    elif user.active_project_id != proj.id:
        user.active_project_id = proj.id
        db.session.commit()
    return proj


def create_project(user, name):
    proj = Project(user_id=user.id, name=name[:128], media_source="mix")
    db.session.add(proj)
    db.session.commit()
    user.active_project_id = proj.id
    db.session.commit()
    return proj


def set_active_project(user, project_id):
    proj = db.session.get(Project, project_id)
    if proj and proj.user_id == user.id:
        user.active_project_id = proj.id
        db.session.commit()
    return proj


def set_media_source(project, source):
    if source in Project.MEDIA_SOURCES:
        project.media_source = source
        db.session.commit()
    return project


def add_project_media(project, path):
    items = json.loads(project.media_json) if project.media_json else []
    items.append(path)
    project.media_json = json.dumps(items)
    db.session.commit()
    return len(items)


def project_media(project):
    return json.loads(project.media_json) if project.media_json else []
