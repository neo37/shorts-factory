"""Credit/billing helpers. One video = CREDITS_PER_VIDEO. New users get NEW_USER_CREDITS."""
from config import Config
from .models import db, User


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
