"""Flask application factory."""
import logging

from flask import Flask, jsonify

from sqlalchemy import inspect, text

from config import Config
from .models import db


# SQLite type map for auto-added columns
_SA_TO_SQLITE = {"INTEGER": "INTEGER", "BIGINT": "BIGINT", "BOOLEAN": "BOOLEAN",
                 "DATETIME": "DATETIME", "TEXT": "TEXT", "VARCHAR": "VARCHAR"}


def _auto_migrate():
    """Add any model columns missing from existing SQLite tables (no data loss).
    db.create_all() creates missing tables but never ALTERs existing ones."""
    insp = inspect(db.engine)
    existing_tables = set(insp.get_table_names())
    for table_name, table in db.metadata.tables.items():
        if table_name not in existing_tables:
            continue
        have = {c["name"] for c in insp.get_columns(table_name)}
        for col in table.columns:
            if col.name in have:
                continue
            ct = col.type.compile(dialect=db.engine.dialect)
            base = ct.split("(")[0].upper()
            sql_type = _SA_TO_SQLITE.get(base, "TEXT")
            try:
                with db.engine.begin() as conn:
                    conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {sql_type}'))
                logging.getLogger("videobot").info("migrated: added %s.%s", table_name, col.name)
            except Exception as e:  # noqa: BLE001
                logging.getLogger("videobot").warning("migrate skip %s.%s: %s", table_name, col.name, e)


def create_app():
    Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__, template_folder="../templates")
    app.config.from_object(Config)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")

    # cap request body to the web-upload limit (+ small overhead)
    app.config["MAX_CONTENT_LENGTH"] = (Config.MAX_WEB_UPLOAD_MB + 8) * 1024 * 1024

    db.init_app(app)

    from .api import api_bp
    app.register_blueprint(api_bp)

    from .uploads import uploads_bp
    app.register_blueprint(uploads_bp)

    from .site import site_bp
    app.register_blueprint(site_bp)

    from .admin import init_admin
    init_admin(app)

    with app.app_context():
        db.create_all()
        _auto_migrate()

    @app.get("/status")
    def status():
        from .models import Job, User, Bot
        return jsonify({
            "users": User.query.count(),
            "bots": Bot.query.count(),
            "jobs": Job.query.count(),
        })

    return app
