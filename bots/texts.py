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
        "✍️ Пришлите промт <b>текстом или голосовым</b>. Можно приложить <b>фото и видео</b> — "
        "они пойдут фоном в сюжет.\n"
        "🗂 В меню ниже выбирайте проект и источник медиа (свои / стоки / микс)."
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


def media_too_big(size_mb: float, upload_url: str = None) -> str:
    base = (f"⚠️ Файл {size_mb:.1f} МБ — больше лимита Telegram для ботов ({MAX_MEDIA_MB} МБ).")
    if upload_url:
        return (base + "\n\n📤 Загрузите его через веб-форму (статус виден там же):\n"
                f"{upload_url}\n\nПосле загрузки вернитесь в бот и отправьте промт.")
    return base + "\nПришлите файл поменьше или сожмите его."


def media_unsupported() -> str:
    return "⚠️ Поддерживаются только фото и видео."


def projects_menu(active_name: str) -> str:
    return (f"🗂 Активный проект: <b>{active_name}</b>\n"
            "Медиа группируются в рамках проекта. Выберите проект или создайте новый.")


def ask_project_name() -> str:
    return "📝 Пришлите название нового проекта одним сообщением."


def project_created(name: str) -> str:
    return f"✅ Проект «<b>{name}</b>» создан и выбран активным."


def source_menu(current: str) -> str:
    label = {"user": "свои медиа", "stock": "внешние стоки", "mix": "микс"}.get(current, "микс")
    return (f"🖼 Источник медиа сейчас: <b>{label}</b>.\n\n"
            "• <b>Свои</b> — используем только ваши фото/видео\n"
            "• <b>Стоки</b> — визуал берём из внешних стоков/генерации\n"
            "• <b>Микс</b> — ваши материалы + стоки\n\nВыберите вариант:")


def source_set(current: str) -> str:
    label = {"user": "свои медиа", "stock": "внешние стоки", "mix": "микс"}.get(current, "микс")
    return f"✅ Источник медиа: <b>{label}</b>."


def ask_media_before_render(source: str, media_count: int) -> str:
    src = "свои медиа" if source == "user" else "микс (свои + стоки)"
    return (
        f"✅ Сценарий утверждён. Источник медиа: <b>{src}</b>.\n\n"
        f"Пришлите <b>фото или видео</b> для фонов сцен (сейчас в подборке: <b>{media_count}</b>), "
        "или возьмите медиа из другого проекта. Когда будете готовы — нажмите <b>▶️ Рендерить</b>."
    )


def render_media_added(count: int) -> str:
    return f"📎 Добавлено (в подборке для рендера: <b>{count}</b>). Пришлите ещё или нажмите ▶️ Рендерить."


def pick_project_prompt() -> str:
    return "📁 Выберите проект, из которого взять медиа:"


def no_other_project_media() -> str:
    return "В других проектах нет медиа. Пришлите фото/видео сами или нажмите ▶️ Рендерить."


def media_taken_from(name: str, count: int) -> str:
    return f"✅ Взято из «<b>{name}</b>». В подборке для рендера: <b>{count}</b>. Нажмите ▶️ Рендерить."


def design_menu(current_label: str) -> str:
    return (f"🎨 Текущий дизайн: <b>{current_label}</b>.\n\n"
            "Выберите готовый стиль или придумаю новый по ссылке на сайт "
            "(подсмотрю цвета и подачу).")


def design_set(label: str) -> str:
    return f"✅ Дизайн: <b>{label}</b>."


def ask_design_url() -> str:
    return "🌐 Пришлите ссылку на сайт — соберу дизайн по его цветам и стилю."


def design_from_url_ok(domain: str) -> str:
    return (f"✅ Готово: собрал дизайн по цветам <b>{domain}</b> и выбрал его активным. "
            "Пришлите промт для видео.")


def design_from_url_fail() -> str:
    return "⚠️ Не удалось разобрать сайт. Выберите готовый стиль или пришлите другую ссылку."


def voice_received() -> str:
    return "🎙 Голосовое получено — распознаю речь, затем соберу сценарий…"


def ask_correction() -> str:
    return "✏️ Пришлите правки одним сообщением (текстом или голосовым) — переделаю сценарий (кредит не спишется)."


def declined() -> str:
    return "❌ Отменено. Пришлите новый промт, когда будете готовы."


def rendering() -> str:
    return "🎥 Видео рендерится, ожидайте…"


def done() -> str:
    return "✅ Готово! Ваше видео ниже."


def error(msg: str) -> str:
    return f"⚠️ Ошибка: {msg}"
