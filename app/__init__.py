"""Flask application factory."""
import logging

from flask import Flask, redirect, jsonify

from config import Config
from .models import db


def create_app():
    Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__, template_folder="../templates")
    app.config.from_object(Config)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")

    db.init_app(app)

    from .api import api_bp
    app.register_blueprint(api_bp)

    from .admin import init_admin
    init_admin(app)

    with app.app_context():
        db.create_all()

    @app.get("/")
    def root():
        return redirect("/admin/")

    @app.get("/status")
    def status():
        from .models import Job, User, Bot
        return jsonify({
            "users": User.query.count(),
            "bots": Bot.query.count(),
            "jobs": Job.query.count(),
        })

    return app
