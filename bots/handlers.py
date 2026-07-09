"""Telegram user flow (aiogram v3). One shared Router across all bots; the design_style
is resolved from the DB by the receiving bot's token.

Prompts may be text OR voice. Voice messages are transcribed via the ASR queue (nemotron),
so all heavy CPU work (render + ASR) is serialized on the single-thread worker.
Media (photos/videos) is grouped per Project; the media source (user/stock/mix) is per Project.
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
from app.models import db, Job, Project
from app import billing
from app.presets import example_paths
from . import texts
from .keyboards import (after_approve_media_kb, design_kb, main_menu_kb, media_source_kb,
                        pick_project_media_kb, projects_kb, review_kb)
from app.presets import THEMES

log = logging.getLogger("videobot.handlers")
router = Router()

_flask_app = None
_token_map = {}                 # token -> {"bot_id", "design_style"}
_awaiting_correction = {}       # (token, tg_id) -> job_id
_awaiting_project_name = set()  # {(token, tg_id)}
_awaiting_render_media = {}     # (token, tg_id) -> job_id  (approved, gathering media before render)
_awaiting_design_url = set()    # {(token, tg_id)}  (waiting for a site URL to derive a theme)


def _menu_kw(user, proj):
    return dict(project_name=proj.name, media_source=proj.media_source,
                design_style=proj.design_style, theme_json=proj.theme_json)

MAX_MEDIA_BYTES = texts.MAX_MEDIA_MB * 1024 * 1024


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


async def _stage_file(bot: Bot, file_id: str, suffix: str, tg_id: int, kind: str) -> str:
    """Download a Telegram file into a per-user staging dir; return local path.
    Raises if the file exceeds Telegram's getFile limit (~20 MB)."""
    dest_dir = Config.DATA_DIR / kind / str(tg_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex}{suffix}"
    tg_file = await bot.get_file(file_id)
    await bot.download_file(tg_file.file_path, destination=str(dest))
    return str(dest)


# ---------------- start / menu ----------------
@router.message(CommandStart())
async def on_start(message: Message, bot: Bot):
    with ctx():
        user = billing.get_or_create_user(
            message.from_user.id, message.from_user.username, message.from_user.first_name)
        proj = billing.get_active_project(user)
        credits, kw = user.credits, _menu_kw(user, proj)
    await message.answer(texts.with_footer(texts.intro(credits)),
                         reply_markup=main_menu_kb(**kw))


# ---------------- project menu ----------------
@router.callback_query(F.data == "proj:menu")
async def on_proj_menu(cb: CallbackQuery, bot: Bot):
    with ctx():
        user = billing.get_or_create_user(cb.from_user.id)
        proj = billing.get_active_project(user)
        projects = Project.query.filter_by(user_id=user.id).all()
        kb = projects_kb(projects, proj.id)
        txt = texts.projects_menu(proj.name)
    await cb.message.answer(texts.with_footer(txt), reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("proj:use:"))
async def on_proj_use(cb: CallbackQuery, bot: Bot):
    pid = int(cb.data.rsplit(":", 1)[1])
    with ctx():
        user = billing.get_or_create_user(cb.from_user.id)
        proj = billing.set_active_project(user, pid)
        kw = _menu_kw(user, proj)
    await cb.message.answer(texts.with_footer(f"✅ Активный проект: <b>{kw['project_name']}</b>"),
                            reply_markup=main_menu_kb(**kw))
    await cb.answer()


@router.callback_query(F.data == "proj:new")
async def on_proj_new(cb: CallbackQuery, bot: Bot):
    _awaiting_project_name.add((bot.token, cb.from_user.id))
    await cb.message.answer(texts.with_footer(texts.ask_project_name()))
    await cb.answer()


# ---------------- media source ----------------
@router.callback_query(F.data == "src:menu")
async def on_src_menu(cb: CallbackQuery, bot: Bot):
    with ctx():
        user = billing.get_or_create_user(cb.from_user.id)
        proj = billing.get_active_project(user)
        cur = proj.media_source
    await cb.message.answer(texts.with_footer(texts.source_menu(cur)), reply_markup=media_source_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("src:") & ~F.data.in_({"src:menu"}))
async def on_src_set(cb: CallbackQuery, bot: Bot):
    src = cb.data.split(":", 1)[1]
    with ctx():
        user = billing.get_or_create_user(cb.from_user.id)
        proj = billing.get_active_project(user)
        billing.set_media_source(proj, src)
        kw = _menu_kw(user, proj)
    await cb.message.answer(texts.with_footer(texts.source_set(src)),
                            reply_markup=main_menu_kb(**kw))
    await cb.answer()


# ---------------- design picker ----------------
@router.callback_query(F.data == "design:menu")
async def on_design_menu(cb: CallbackQuery, bot: Bot):
    with ctx():
        user = billing.get_or_create_user(cb.from_user.id)
        proj = billing.get_active_project(user)
        cur = proj.design_style
        label = "из сайта" if proj.theme_json else THEMES.get(cur, THEMES["businesspad-dark"])["label"]
    await cb.message.answer(texts.with_footer(texts.design_menu(label)),
                            reply_markup=design_kb(cur))
    await cb.answer()


@router.callback_query(F.data.startswith("design:set:"))
async def on_design_set(cb: CallbackQuery, bot: Bot):
    slug = cb.data.split(":", 2)[2]
    with ctx():
        user = billing.get_or_create_user(cb.from_user.id)
        proj = billing.get_active_project(user)
        billing.set_design(proj, slug)
        label = THEMES.get(slug, THEMES["businesspad-dark"])["label"]
        kw = _menu_kw(user, proj)
    await cb.message.answer(texts.with_footer(texts.design_set(label)), reply_markup=main_menu_kb(**kw))
    await cb.answer()


@router.callback_query(F.data == "design:fromurl")
async def on_design_fromurl(cb: CallbackQuery, bot: Bot):
    _awaiting_design_url.add((bot.token, cb.from_user.id))
    await cb.message.answer(texts.with_footer(texts.ask_design_url()))
    await cb.answer()


# ---------------- review buttons ----------------
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


async def _start_render(bot: Bot, chat_id, job_id, key):
    from app.tasks import render_final
    with ctx():
        job = db.session.get(Job, job_id)
        job.status = "queued"
        db.session.commit()
    _awaiting_render_media.pop(key, None)
    _awaiting_correction.pop(key, None)
    await _enqueue(render_final, job_id)
    await bot.send_message(chat_id, texts.with_footer(texts.rendering()))


@router.callback_query(F.data.startswith("approve:"))
async def on_approve(cb: CallbackQuery, bot: Bot):
    job_id = int(cb.data.split(":", 1)[1])
    key = (bot.token, cb.from_user.id)
    with ctx():
        job = db.session.get(Job, job_id)
        if not job or job.status != "awaiting_user":
            await cb.answer("Уже обработано")
            return
        source = job.media_source or "mix"
        # seed the render media from the job's project
        proj = db.session.get(Project, job.project_id) if job.project_id else None
        if proj:
            billing.set_job_media(job, billing.project_media(proj))
        media_count = len(billing.job_media(job))

    # stock → render right away; user/mix → gather media first
    if source == "stock":
        await _start_render(bot, cb.message.chat.id, job_id, key)
    else:
        _awaiting_render_media[key] = job_id
        await cb.message.answer(
            texts.with_footer(texts.ask_media_before_render(source, media_count)),
            reply_markup=after_approve_media_kb(job_id))
    await cb.answer()


@router.callback_query(F.data.startswith("render:"))
async def on_render(cb: CallbackQuery, bot: Bot):
    job_id = int(cb.data.split(":", 1)[1])
    key = (bot.token, cb.from_user.id)
    with ctx():
        job = db.session.get(Job, job_id)
        if not job or job.status not in ("awaiting_user",):
            await cb.answer("Уже в работе")
            return
    await _start_render(bot, cb.message.chat.id, job_id, key)
    await cb.answer()


@router.callback_query(F.data.startswith("pickproj:"))
async def on_pickproj(cb: CallbackQuery, bot: Bot):
    job_id = int(cb.data.split(":", 1)[1])
    with ctx():
        job = db.session.get(Job, job_id)
        user = billing.get_or_create_user(cb.from_user.id)
        # other projects of this user that actually have media
        rows = []
        for p in Project.query.filter_by(user_id=user.id).all():
            if p.id == job.project_id:
                continue
            cnt = len(billing.project_media(p))
            if cnt:
                rows.append((p, cnt))
    if not rows:
        await cb.message.answer(texts.with_footer(texts.no_other_project_media()),
                                reply_markup=after_approve_media_kb(job_id))
    else:
        await cb.message.answer(texts.with_footer(texts.pick_project_prompt()),
                                reply_markup=pick_project_media_kb(job_id, rows))
    await cb.answer()


@router.callback_query(F.data.startswith("pickmedia:"))
async def on_pickmedia(cb: CallbackQuery, bot: Bot):
    _, job_id, proj_id = cb.data.split(":")
    job_id, proj_id = int(job_id), int(proj_id)
    with ctx():
        job = db.session.get(Job, job_id)
        proj = db.session.get(Project, proj_id)
        merged = billing.job_media(job) + billing.project_media(proj)
        # de-dup preserving order
        seen, out = set(), []
        for m in merged:
            if m not in seen:
                seen.add(m); out.append(m)
        billing.set_job_media(job, out)
        name, count = proj.name, len(out)
    await cb.message.answer(texts.with_footer(texts.media_taken_from(name, count)),
                            reply_markup=after_approve_media_kb(job_id))
    await cb.answer()


@router.callback_query(F.data.startswith("backmedia:"))
async def on_backmedia(cb: CallbackQuery, bot: Bot):
    job_id = int(cb.data.split(":", 1)[1])
    with ctx():
        job = db.session.get(Job, job_id)
        count = len(billing.job_media(job))
        source = job.media_source or "mix"
    await cb.message.answer(texts.with_footer(texts.ask_media_before_render(source, count)),
                            reply_markup=after_approve_media_kb(job_id))
    await cb.answer()


# ---------------- media uploads (grouped per project) ----------------
async def _too_big_link(message: Message, size: int):
    """Mint a web-upload link for the user's active project and tell them to use it."""
    with ctx():
        user = billing.get_or_create_user(message.from_user.id)
        proj = billing.get_active_project(user)
        url = billing.make_upload_link(user, proj)
    await message.answer(texts.with_footer(texts.media_too_big((size or 0) / 1024 / 1024, url)),
                         disable_web_page_preview=False)


async def _add_media(bot: Bot, message: Message, file_id: str, suffix: str, size: int):
    if size and size > MAX_MEDIA_BYTES:
        await _too_big_link(message, size)
        return
    try:
        path = await _stage_file(bot, file_id, suffix, message.from_user.id, "media")
    except Exception as e:  # noqa: BLE001 — >20MB or transient: fall back to web upload
        log.warning("media download failed (%s); offering web upload", e)
        await _too_big_link(message, size)
        return
    key = (bot.token, message.from_user.id)
    render_job_id = _awaiting_render_media.get(key)
    with ctx():
        user = billing.get_or_create_user(message.from_user.id)
        proj = billing.get_active_project(user)
        billing.add_project_media(proj, path)
        if render_job_id:                       # gathering media for an approved job
            job = db.session.get(Job, render_job_id)
            count = billing.add_job_media(job, path)
        else:
            count = len(billing.project_media(proj))
    if render_job_id:
        await message.answer(texts.with_footer(texts.render_media_added(count)),
                             reply_markup=after_approve_media_kb(render_job_id))
    else:
        await message.answer(texts.with_footer(texts.media_added(count)))


@router.message(F.photo)
async def on_photo(message: Message, bot: Bot):
    photo = message.photo[-1]
    await _add_media(bot, message, photo.file_id, ".jpg", photo.file_size or 0)


@router.message(F.video | F.animation | F.document)
async def on_video(message: Message, bot: Bot):
    obj = message.video or message.animation or message.document
    mime = getattr(obj, "mime_type", "") or ""
    is_video = bool(message.video or message.animation) or mime.startswith("video/")
    is_image = mime.startswith("image/")
    if not (is_video or is_image):
        await message.answer(texts.with_footer(texts.media_unsupported()))
        return
    await _add_media(bot, message, obj.file_id, ".mp4" if is_video else ".jpg", obj.file_size or 0)


# ---------------- voice prompt (ASR via queue) ----------------
@router.message(F.voice | F.audio)
async def on_voice(message: Message, bot: Bot):
    from app.tasks import process_voice_prompt
    obj = message.voice or message.audio
    size = obj.file_size or 0
    if size > MAX_MEDIA_BYTES:
        await message.answer(texts.with_footer(texts.media_too_big(size / 1024 / 1024)))
        return
    key = (bot.token, message.from_user.id)
    binfo = _token_map.get(bot.token, {})
    try:
        voice_path = await _stage_file(bot, obj.file_id, ".ogg", message.from_user.id, "voice")
    except Exception as e:  # noqa: BLE001
        await message.answer(texts.with_footer(texts.error(f"не удалось скачать голосовое: {e}")))
        return

    with ctx():
        user = billing.get_or_create_user(
            message.from_user.id, message.from_user.username, message.from_user.first_name)
        proj = billing.get_active_project(user)

        # voice as a correction to an existing job — no charge
        if key in _awaiting_correction:
            job = db.session.get(Job, _awaiting_correction[key])
            if job:
                job.voice_path = voice_path
                job.status = "queued"
                db.session.commit()
                jid = job.id
                _awaiting_correction.pop(key, None)
                await message.answer(texts.with_footer(texts.voice_received()))
                await _enqueue(process_voice_prompt, jid)
                return

        # new voice prompt — charge 1 credit
        if not billing.has_credit(user):
            await message.answer(texts.with_footer(texts.no_credits()),
                                 reply_markup=main_menu_kb(**_menu_kw(user, proj)))
            return
        billing.charge(user)
        media = billing.project_media(proj)
        job = Job(
            bot_id=binfo.get("bot_id"), user_id=user.id, project_id=proj.id,
            telegram_id=user.telegram_id, chat_id=message.chat.id,
            design_style=proj.design_style, theme_json=proj.theme_json,
            media_source=proj.media_source,
            media_json=json.dumps(media) if media else None,
            voice_path=voice_path,
            watermark=billing.watermark_for(user), status="queued",
        )
        db.session.add(job)
        db.session.commit()
        jid = job.id
    await message.answer(texts.with_footer(texts.voice_received()))
    await _enqueue(process_voice_prompt, jid)


# ---------------- text (project name / correction / new prompt) ----------------
@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message, bot: Bot):
    from app.tasks import process_prompt
    key = (bot.token, message.from_user.id)
    binfo = _token_map.get(bot.token, {})

    # awaiting a site URL to derive a design theme
    if key in _awaiting_design_url:
        _awaiting_design_url.discard(key)
        from app import webfetch
        from urllib.parse import urlparse
        url = message.text.strip()
        loop = asyncio.get_event_loop()
        theme = await loop.run_in_executor(None, lambda: webfetch.extract_theme(url))
        with ctx():
            user = billing.get_or_create_user(message.from_user.id)
            proj = billing.get_active_project(user)
            if theme:
                billing.set_custom_theme(proj, theme)
                kw = _menu_kw(user, proj)
                dom = urlparse(url).netloc or url
                await message.answer(texts.with_footer(texts.design_from_url_ok(dom)),
                                     reply_markup=main_menu_kb(**kw))
            else:
                await message.answer(texts.with_footer(texts.design_from_url_fail()),
                                     reply_markup=design_kb(proj.design_style))
        return

    # awaiting a new project name
    if key in _awaiting_project_name:
        _awaiting_project_name.discard(key)
        with ctx():
            user = billing.get_or_create_user(message.from_user.id)
            proj = billing.create_project(user, message.text)
            kw = _menu_kw(user, proj)
        await message.answer(texts.with_footer(texts.project_created(kw["project_name"])),
                             reply_markup=main_menu_kb(**kw))
        return

    with ctx():
        user = billing.get_or_create_user(
            message.from_user.id, message.from_user.username, message.from_user.first_name)
        proj = billing.get_active_project(user)

        # correction to an existing job — no charge
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

        # new prompt — charge 1 credit
        if not billing.has_credit(user):
            await message.answer(texts.with_footer(texts.no_credits()),
                                 reply_markup=main_menu_kb(**_menu_kw(user, proj)))
            return
        billing.charge(user)
        media = billing.project_media(proj)
        job = Job(
            bot_id=binfo.get("bot_id"), user_id=user.id, project_id=proj.id,
            telegram_id=user.telegram_id, chat_id=message.chat.id,
            design_style=proj.design_style, theme_json=proj.theme_json,
            media_source=proj.media_source,
            media_json=json.dumps(media) if media else None,
            prompt=message.text,
            watermark=billing.watermark_for(user), status="queued",
        )
        db.session.add(job)
        db.session.commit()
        jid = job.id
    await message.answer(texts.with_footer(texts.generating()))
    await _enqueue(process_prompt, jid)
