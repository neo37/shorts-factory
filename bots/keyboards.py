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


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Связаться / Пополнить баланс", url=Config.TOPUP_CONTACT_URL)],
    ])
