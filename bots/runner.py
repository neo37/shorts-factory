"""Multibot runner: loads active bot tokens from the DB and polls them all in one process.
Run: python -m bots.runner
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app import create_app
from app.models import Bot as BotRow
from . import handlers

log = logging.getLogger("videobot.runner")


async def _main():
    flask_app = create_app()
    with flask_app.app_context():
        rows = BotRow.query.filter_by(is_active=True).all()
        token_map = {r.token: {"bot_id": r.id, "design_style": r.design_style} for r in rows}

    if not token_map:
        log.warning("No active bots in DB. Add one in the admin panel (Боты) and restart.")
        return

    handlers.init(flask_app, token_map)
    dp = Dispatcher()
    dp.include_router(handlers.router)

    bots = [Bot(t, default=DefaultBotProperties(parse_mode=ParseMode.HTML)) for t in token_map]
    log.info("Starting %d bot(s)…", len(bots))
    await dp.start_polling(*bots)


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(_main())


if __name__ == "__main__":
    main()
