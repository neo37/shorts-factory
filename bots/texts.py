"""User-facing bot copy. The footer link is permanent and appended to every message."""
from config import Config

FOOTER = f"\n\n— — —\n🔗 {Config.PROJECT_FOOTER_URL}"


def with_footer(text: str) -> str:
    """Append the non-erasable project footer to any outgoing text."""
    return text.rstrip() + FOOTER


def intro(credits: int) -> str:
    return (
        "👋 <b>Генератор вертикальных видео (Shorts)</b>\n\n"
        "Опишите тему — я пришлю <b>сюжет, раскадровку и черновик озвучки</b>. "
        "Можно дополнить или переделать, а после утверждения — соберу видео в фирменном стиле.\n\n"
        f"💳 Чтобы убрать watermark и разблокировать генерацию — пополните баланс: "
        f"<b>{Config.TOPUP_RUB} ₽ за {Config.TOPUP_VIDEOS} видео</b>.\n"
        f"На вашем балансе: <b>{credits}</b> кредитов.\n\n"
        "✍️ Просто пришлите текстовый промт, чтобы начать."
    )


def no_credits() -> str:
    return (
        "⛔️ На балансе <b>0</b> кредитов.\n\n"
        f"Пополните баланс — {Config.TOPUP_RUB} ₽ за {Config.TOPUP_VIDEOS} видео. "
        "Нажмите «Связаться / Пополнить баланс»."
    )


def generating() -> str:
    return "⏳ Генерирую сюжет и черновик озвучки…"


def storyboard_message(storyboard: dict, vo: str, credits: int) -> str:
    lines = [f"🎬 <b>{storyboard.get('title', 'Сюжет')}</b>"]
    hook = storyboard.get("hook")
    if hook:
        lines.append(f"<i>{hook}</i>")
    lines.append("\n<b>Раскадровка:</b>")
    for i, sc in enumerate(storyboard.get("scenes", []), 1):
        lines.append(f"{i}. <b>{sc.get('headline','')}</b> — {sc.get('caption','')}")
    lines.append("\n<b>Черновик озвучки:</b>")
    lines.append(vo or "—")
    lines.append(f"\n💳 Баланс: <b>{credits}</b> кредитов")
    return "\n".join(lines)


MAX_MEDIA_MB = 20  # Telegram Bot API getFile download limit (standard, non-local server)


def media_added(count: int) -> str:
    return (
        f"📎 Медиа добавлено (в подборке: <b>{count}</b>). "
        "Эти фото/видео пойдут фоном в сюжет.\n"
        "Пришлите текстовый промт, чтобы собрать сценарий с этим материалом."
    )


def media_too_big(size_mb: float) -> str:
    return (
        f"⚠️ Файл {size_mb:.1f} МБ — больше лимита Telegram для ботов ({MAX_MEDIA_MB} МБ).\n"
        "Пришлите файл поменьше (можно сжать), либо загрузку крупных файлов "
        "подключим через self-hosted Bot API (до 2 ГБ)."
    )


def media_unsupported() -> str:
    return "⚠️ Поддерживаются только фото и видео."


def ask_correction() -> str:
    return "✏️ Пришлите правки одним сообщением — переделаю сценарий (кредит не спишется)."


def declined() -> str:
    return "❌ Отменено. Пришлите новый промт, когда будете готовы."


def rendering() -> str:
    return "🎥 Видео рендерится, ожидайте…"


def done() -> str:
    return "✅ Готово! Ваше видео ниже."


def error(msg: str) -> str:
    return f"⚠️ Ошибка: {msg}"
