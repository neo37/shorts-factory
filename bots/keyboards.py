"""Inline keyboards. NOTE: an [✅ Утвердить] button is added to the four requested
buttons because the approval step (TZ §2.6) needs an explicit trigger."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import Config


def review_kb(job_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Утвердить", callback_data=f"approve:{job_id}")
    b.button(text="✏️ Дополнить", callback_data=f"amend:{job_id}")
    b.button(text="❌ Отказаться", callback_data=f"decline:{job_id}")
    b.button(text="🎬 Смотреть примеры", callback_data=f"examples:{job_id}")
    b.button(text="💳 Пополнить баланс", url=Config.TOPUP_CONTACT_URL)
    b.adjust(1, 2, 1, 1)
    return b.as_markup()


def main_menu_kb(project_name: str = None, media_source: str = None) -> InlineKeyboardMarkup:
    src_label = {"user": "свои медиа", "stock": "стоки", "mix": "микс"}.get(media_source or "mix", "микс")
    rows = [
        [InlineKeyboardButton(text=f"🗂 Проект: {project_name or 'Мой проект'}",
                              callback_data="proj:menu")],
        [InlineKeyboardButton(text=f"🖼 Источник медиа: {src_label}", callback_data="src:menu")],
        [InlineKeyboardButton(text="💳 Связаться / Пополнить баланс", url=Config.TOPUP_CONTACT_URL)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def media_source_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Мои фото/видео", callback_data="src:user")],
        [InlineKeyboardButton(text="🌐 Внешние стоки", callback_data="src:stock")],
        [InlineKeyboardButton(text="🔀 Микс (свои + стоки)", callback_data="src:mix")],
    ])


def after_approve_media_kb(job_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📁 Взять из другого проекта", callback_data=f"pickproj:{job_id}")
    b.button(text="▶️ Рендерить", callback_data=f"render:{job_id}")
    b.adjust(1)
    return b.as_markup()


def pick_project_media_kb(job_id: int, projects) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p, cnt in projects:
        b.button(text=f"{p.name} · {cnt} медиа", callback_data=f"pickmedia:{job_id}:{p.id}")
    b.button(text="◀️ Назад", callback_data=f"backmedia:{job_id}")
    b.adjust(1)
    return b.as_markup()


def projects_kb(projects, active_id) -> InlineKeyboardMarkup:
    rows = []
    for p in projects:
        mark = "✅ " if p.id == active_id else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{p.name}", callback_data=f"proj:use:{p.id}")])
    rows.append([InlineKeyboardButton(text="➕ Новый проект", callback_data="proj:new")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
