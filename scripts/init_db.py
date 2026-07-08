"""Create tables and seed presets + a first external API key.
Run:  .venv/bin/python -m scripts.init_db
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.models import db, Preset, ApiKey
from app.presets import PRESETS


def main():
    app = create_app()
    with app.app_context():
        db.create_all()

        for slug, meta in PRESETS.items():
            if not Preset.query.filter_by(slug=slug).first():
                db.session.add(Preset(
                    slug=slug, title=meta["title"], description=meta["description"],
                    example_render=(meta.get("examples") or [""])[0],
                ))
        db.session.commit()

        if not ApiKey.query.first():
            k = ApiKey.generate("default-external")
            db.session.add(k)
            db.session.commit()
            print("Created external API key:", k.key)
        else:
            print("API key already exists.")

        print("Presets:", [p.slug for p in Preset.query.all()])
        print("DB ready at:", app.config["SQLALCHEMY_DATABASE_URI"])
        print("\nNext: add a Telegram bot token in the admin panel (Боты),")
        print("set its design_style (e.g. businesspad-dark), then run the bots runner.")


if __name__ == "__main__":
    main()
