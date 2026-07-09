"""Push job status updates back to the user. Called from the Celery worker process,
so it spins up a short-lived Bot and its own event loop (no shared loop with the runner).
"""
import asyncio
import logging

from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.models import db, Bot as BotRow
from . import texts
from .keyboards import done_kb, review_kb

log = logging.getLogger("videobot.notify")


async def _send(job):
    bot_row = db.session.get(BotRow, job.bot_id)
    if not bot_row:
        log.warning("no bot row for job %s", job.id)
        return
    bot = Bot(bot_row.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        if job.status == "awaiting_user":
            import json
            sb = json.loads(job.storyboard_json or "{}")
            credits = job.user.credits if job.user else 0
            await bot.send_message(
                job.chat_id,
                texts.with_footer(texts.storyboard_message(sb, job.vo_draft or "", credits)),
                reply_markup=review_kb(job.id),
            )
        elif job.status == "rendering":
            await bot.send_message(job.chat_id, texts.with_footer(texts.rendering()))
        elif job.status == "done":
            if job.output_path:
                await bot.send_video(job.chat_id, FSInputFile(job.output_path),
                                     caption=texts.with_footer(texts.done()),
                                     reply_markup=done_kb(job.id))
            else:
                await bot.send_message(job.chat_id, texts.with_footer(texts.done()),
                                       reply_markup=done_kb(job.id))
        elif job.status == "error":
            await bot.send_message(job.chat_id, texts.with_footer(texts.error(job.error or "unknown")))
    finally:
        await bot.session.close()


def notify_job(job):
    """Synchronous entry point for Celery tasks."""
    asyncio.run(_send(job))
