"""Support chat labels. The database stores the same category keys as the Mini App."""
CATEGORIES = {
    "connection": ("Подключение", "Connection"),
    "speed": ("Скорость", "Speed"),
    "payment": ("Оплата", "Payment"),
    "subscription": ("Подписка", "Subscription"),
    "other": ("Другое", "Other"),
}

LABELS = {
    **CATEGORIES,
    "hint": (
        "Если вы покупали подписку вне Telegram-бота, укажите в обращении номер заказа, email, использованный при покупке, или ссылку на подписку. Достаточно одного из них — так поддержка быстрее найдёт вашу покупку.",
        "If you bought your subscription outside the Telegram bot, include your order number, purchase email or subscription link. Any one of these will help support find your purchase faster.",
    ),
    "welcome": (
        "👋 <b>Здравствуйте! Это поддержка {brand}.</b>\n\nЗдесь можно задать вопрос о подключении, оплате или подписке и приложить скриншот. Оператор ответит в этом чате.\n\nСоздайте обращение или откройте прежнюю переписку в разделе «Мои обращения».",
        "👋 <b>Welcome to {brand} support!</b>\n\nAsk us about your connection, payment or subscription, and attach a screenshot if it helps. Our team will reply here.\n\nCreate a ticket or open a previous conversation in My tickets.",
    ),
    "tip_title": ("Подсказка", "Tip"),
    "ticket": ("Обращение", "Ticket"),
    "choose_ticket": ("Выберите обращение, чтобы прочитать переписку или ответить.", "Choose a ticket to read the conversation or reply."),
    "next": ("Далее", "Next"),
    "back": ("Назад", "Back"),
    "new": ("✍️ Создать обращение", "✍️ Create ticket"),
    "list": ("📂 Мои обращения", "📂 My tickets"),
    "empty": ("У вас пока нет обращений.", "You have no tickets yet."),
    "category": ("✍️ <b>Новое обращение</b>\n\nС чем нужна помощь?", "✍️ <b>New ticket</b>\n\nWhat can we help you with?"),
    "describe": ("Опишите проблему текстом или в подписи к изображению.", "Describe the issue in a message or image caption."),
    "compose": ("Можно приложить до трёх изображений по 5 МиБ. Когда всё готово, нажмите «Отправить».", "Attach up to three images, up to 5 MiB each. Tap Send when ready."),
    "draft": ("В черновике: {chars}/4000 символов, изображений: {count}/3.", "Draft: {chars}/4000 characters, {count}/3 images."),
    "send": ("📤 Отправить", "📤 Send"),
    "cancel": ("Отмена", "Cancel"),
    "reset": ("🗑 Убрать изображения", "🗑 Remove images"),
    "text_limit": ("Максимум 4000 символов. Отправьте более короткий текст.", "Use up to 4000 characters. Send a shorter text."),
    "replace": ("Чтобы изменить текст, пришлите его заново.", "Send a new text to replace the draft text."),
    "invalid": ("Проверьте вложения: до трёх файлов JPEG, PNG, WebP или GIF, каждый до 5 МиБ. Можно убрать изображения и выбрать их заново.", "Check your images: up to three JPEG, PNG, WebP or GIF files, each up to 5 MiB. You can remove the images and select them again."),
    "download": ("Не удалось скачать вложение. Попробуйте ещё раз.", "Could not download the attachment. Please try again."),
    "need_text": ("Добавьте описание обращения.", "Add a description of the issue."),
    "need_reply": ("Добавьте текст или изображение.", "Add text or an image."),
    "limit": ("У вас уже пять активных обращений.", "You already have five active tickets."),
    "closed": ("✅ Закрыто", "✅ Closed"),
    "open": ("🟢 Открыто", "🟢 Open"),
    "waiting_user": ("💬 Ожидает вашего ответа", "💬 Waiting for your reply"),
    "in_progress": ("🔎 В работе", "🔎 In progress"),
    "unavailable": ("Обращение или вложение недоступно.", "Ticket or attachment unavailable."),
    "expired": ("Срок повторного открытия истёк.", "The reopening period has expired."),
    "stale": ("Эта кнопка устарела. Используйте последнее сообщение бота.", "This button has expired. Use the latest message from the bot."),
    "reply": ("✍️ Ответить", "✍️ Reply"),
    "resolve": ("✅ Решено", "✅ Mark resolved"),
    "reopen": ("↩️ Открыть снова", "↩️ Reopen"),
    "older": ("Раньше", "Earlier"),
    "newer": ("Позже", "Later"),
    "user": ("Вы", "You"),
    "admin": ("Поддержка", "Support"),
    "image": ("Изображение", "Image"),
    "sent": ("✅ Сообщение отправлено в обращение <b>#{id}</b>.", "✅ Message sent to ticket <b>#{id}</b>."),
    "view": ("Открыть обращение", "Open ticket"),
}


def label(lang, key):
    return LABELS[key][lang == "en"]
