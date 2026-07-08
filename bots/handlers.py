"""Telegram user flow (aiogram v3). One shared Router across all bots; the design_style
is resolved from the DB by the receiving bot's token.
"""
import asyncio
import json
import logging
import uuid
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, FSInputFile, Message

from config import Config
from app.models import db, Job
from app import billing
from app.presets import example_paths
from . import texts
from .keyboards import main_menu_kb, review_kb

log = logging.getLogger("videobot.handlers")
router = Router()

_flask_app = None
_token_map = {}                 # token -> {"bot_id", "design_style"}
_awaiting_correction = {}       # (token, tg_id) -> job_id
_media_basket = {}              # (token, tg_id) -> [staged file paths]

MAX_MEDIA_BYTES = texts.MAX_MEDIA_MB * 1024 * 1024


async def _stage_media(bot: Bot, file_id: str, suffix: str, tg_id: int) -> str:
    """Download a Telegram file into the per-user staging dir; return local path."""
    dest_dir = Config.DATA_DIR / "media" / str(tg_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex}{suffix}"
    tg_file = await bot.get_file(file_id)          # raises if > 20 MB (Telegram side)
    await bot.download_file(tg_file.file_path, destination=str(dest))
    return str(dest)


def init(flask_app, token_map):
    global _flask_app, _token_map
    _flask_app = flask_app
    _token_map = token_map


def ctx():
    return _flask_app.app_context()


async def _enqueue(task, *args):
    """Enqueue a Celery task without blocking the event loop (works in eager & broker mode)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: task.delay(*args))


@router.message(CommandStart())
async def on_start(message: Message, bot: Bot):
    with ctx():
        user = billing.get_or_create_user(
            message.from_user.id, message.from_user.username, message.from_user.first_name)
        credits = user.credits
    await message.answer(texts.with_footer(texts.intro(credits)), reply_markup=main_menu_kb())


@router.callback_query(F.data.startswith("amend:"))
async def on_amend(cb: CallbackQuery, bot: Bot):
    job_id = int(cb.data.split(":", 1)[1])
    _awaiting_correction[(bot.token, cb.from_user.id)] = job_id
    await cb.message.answer(texts.with_footer(texts.ask_correction()))
    await cb.answer()


@router.callback_query(F.data.startswith("decline:"))
async def on_decline(cb: CallbackQuery, bot: Bot):
    job_id = int(cb.data.split(":", 1)[1])
    with ctx():
        job = db.session.get(Job, job_id)
        if job:
            job.status = "cancelled"
            db.session.commit()
    _awaiting_correction.pop((bot.token, cb.from_user.id), None)
    await cb.message.answer(texts.with_footer(texts.declined()))
    await cb.answer()


@router.callback_query(F.data.startswith("examples:"))
async def on_examples(cb: CallbackQuery, bot: Bot):
    from config import Config
    style = _token_map.get(bot.token, {}).get("design_style", "businesspad-dark")
    sent = 0
    for rel in example_paths(style):
        p = Config.OPENMONTAGE_DIR / rel
        if p.exists():
            try:
                await bot.send_video(cb.message.chat.id, FSInputFile(str(p)))
                sent += 1
            except Exception as e:  # noqa: BLE001
                log.warning("example send failed: %s", e)
    if not sent:
        await cb.message.answer(texts.with_footer("Примеры пока недоступны."))
    await cb.answer()


@router.callback_query(F.data.startswith("approve:"))
async def on_approve(cb: CallbackQuery, bot: Bot):
    from app.tasks import render_final
    job_id = int(cb.data.split(":", 1)[1])
    with ctx():
        job = db.session.get(Job, job_id)
        if not job or job.status not in ("awaiting_user",):
            await cb.answer("Уже обработано", show_alert=False)
            return
        job.status = "queued"
        db.session.commit()
    await _enqueue(render_final, job_id)
    _awaiting_correction.pop((bot.token, cb.from_user.id), None)
    await cb.message.answer(texts.with_footer(texts.rendering()))
    await cb.answer()


@router.message(F.photo)
async def on_photo(message: Message, bot: Bot):
    photo = message.photo[-1]  # largest size; Telegram-compressed, always small
    try:
        path = await _stage_media(bot, photo.file_id, ".jpg", message.from_user.id)
    except Exception as e:  # noqa: BLE001
        log.warning("photo download failed: %s", e)
        await message.answer(texts.with_footer(texts.media_too_big(
            (photo.file_size or 0) / 1024 / 1024)))
        return
    basket = _media_basket.setdefault((bot.token, message.from_user.id), [])
    basket.append(path)
    await message.answer(texts.with_footer(texts.media_added(len(basket))))


@router.message(F.video | F.document | F.animation)
async def on_video(message: Message, bot: Bot):
    obj = message.video or message.animation or message.document
    mime = getattr(obj, "mime_type", "") or ""
    is_video = bool(message.video or message.animation) or mime.startswith("video/")
    is_image = mime.startswith("image/")
    if not (is_video or is_image):
        await message.answer(texts.with_footer(texts.media_unsupported()))
        return
    size = obj.file_size or 0
    if size > MAX_MEDIA_BYTES:
        await message.answer(texts.with_footer(texts.media_too_big(size / 1024 / 1024)))
        return
    suffix = ".mp4" if is_video else ".jpg"
    try:
        path = await _stage_media(bot, obj.file_id, suffix, message.from_user.id)
    except Exception as e:  # noqa: BLE001
        log.warning("media download failed: %s", e)
        await message.answer(texts.with_footer(texts.media_too_big(size / 1024 / 1024)))
        return
    basket = _media_basket.setdefault((bot.token, message.from_user.id), [])
    basket.append(path)
    await message.answer(texts.with_footer(texts.media_added(len(basket))))


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message, bot: Bot):
    from app.tasks import process_prompt
    key = (bot.token, message.from_user.id)
    binfo = _token_map.get(bot.token, {})
    with ctx():
        user = billing.get_or_create_user(
            message.from_user.id, message.from_user.username, message.from_user.first_name)

        # correction path — no charge
        if key in _awaiting_correction:
            job = db.session.get(Job, _awaiting_correction[key])
            if job:
                job.corrections = ((job.corrections or "") + "\n" + message.text).strip()
                job.status = "queued"
                db.session.commit()
                jid = job.id
                _awaiting_correction.pop(key, None)
                await message.answer(texts.with_footer(texts.generating()))
                await _enqueue(process_prompt, jid)
                return

        # new prompt path — charge 1 credit
        if not billing.has_credit(user):
            await message.answer(texts.with_footer(texts.no_credits()), reply_markup=main_menu_kb())
            return
        billing.charge(user)
        media = _media_basket.pop(key, [])
        job = Job(
            bot_id=binfo.get("bot_id"),
            user_id=user.id,
            telegram_id=user.telegram_id,
            chat_id=message.chat.id,
            design_style=binfo.get("design_style", "businesspad-dark"),
            prompt=message.text,
            media_json=json.dumps(media) if media else None,
            watermark=billing.watermark_for(user),
            status="queued",
        )
        db.session.add(job)
        db.session.commit()
        jid = job.id
    await message.answer(texts.with_footer(texts.generating()))
    await _enqueue(process_prompt, jid)
