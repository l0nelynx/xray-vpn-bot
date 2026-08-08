import type { Messages } from "./types";

export const ru: Messages = {
  // tabs
  "tabs.home": "Главная",
  "tabs.devices": "Устройства",
  "tabs.support": "Поддержка",
  "tabs.account": "Аккаунт",

  // app
  "app.error.genericTitle": "Ошибка",
  "app.error.noData": "Нет данных",

  // common
  "common.back": "Назад",
  "common.cancel": "Отмена",
  "common.delete": "Удалить",
  "common.refresh": "Обновить",
  "common.toHome": "На главную",
  "common.emDash": "—",
  "common.daysShort": "{count} дн.",
  "common.gb": "ГБ",
  "common.gbUsedOfLimit": "{used} / {limit} ГБ",
  "common.gbUsed": "{used} ГБ",
  "common.error": "Ошибка",

  // subscription
  "subscription.status.active": "Активна",
  "subscription.status.expired": "Истекла",
  "subscription.status.disabled": "Отключена",
  "subscription.status.limited": "Ограничена",
  "subscription.status.unavailable": "Недоступна",
  "subscription.daysLeft": "дней осталось",
  "subscription.devices": "Устройства",
  "subscription.traffic": "Трафик",
  "subscription.expires": "Истекает",

  // tickets status
  "tickets.status.open": "Открыт",
  "tickets.status.inProgress": "В работе",
  "tickets.status.closed": "Закрыт",

  // home
  "home.titleFallback": "Подписка",
  "home.subtitle": "VPN аккаунт",
  "home.refreshAria": "Обновить",
  "home.connect": "Подключиться",
  "home.extend": "Продлить подписку",
  "home.buy": "Купить подписку",
  "home.telegramProxy": "Telegram Прокси",
  "home.emptyTitle": "Нет активной подписки",
  "home.emptyBody": "Выберите тариф или активируйте пробный доступ",
  "home.tryFree": "Попробовать бесплатно",
  "home.allSubscriptions": "Все подписки · {count}",

  // subscriptions
  "subscriptions.title": "Мои подписки",
  "subscriptions.subtitle": "Выберите подписку для подключения или продления",
  "subscriptions.loadError": "Не удалось загрузить подписки",
  "subscriptions.empty": "У аккаунта пока нет привязанных подписок",
  "subscriptions.primary": "Основная",
  "subscriptions.makePrimary": "Сделать основной",
  "subscriptions.primaryChanged": "Основная подписка изменена",
  "subscriptions.connect": "Подключить",
  "subscriptions.renew": "Продлить",
  "subscriptions.unavailable": "Remnawave временно недоступен. Привязка сохранена.",
  "subscriptions.notFound": "Подписка не найдена или больше не привязана к аккаунту",
  "subscriptions.fallbackLabel": "Подписка #{id}",

  // devices
  "devices.title": "Мои устройства",
  "devices.refreshAria": "Обновить",
  "devices.empty": "Нет привязанных устройств",
  "devices.fallbackName": "Устройство",
  "devices.os": "ОС: {version}",
  "devices.added": "Добавлено: {date}",
  "devices.toast.deleted": "Устройство удалено",
  "devices.toast.deleteFailed": "Не удалось удалить устройство",
  "devices.confirm.title": "Удалить устройство?",
  "devices.confirm.body": "После удаления потребуется новая авторизация.",
  "devices.confirm.cancel": "Отмена",
  "devices.confirm.delete": "Удалить",

  // free trial
  "freeTrial.title.telemt": "Telegram Прокси",
  "freeTrial.title.vpn": "Попробовать бесплатно",
  "freeTrial.desc.telemt":
    "Подпишитесь на наш канал, чтобы получить бесплатный Telegram-прокси.",
  "freeTrial.desc.vpn":
    "Подпишитесь на наш канал, чтобы получить бесплатную подписку VPN.",
  "freeTrial.success.proxyReady": "Прокси готов",
  "freeTrial.success.subActive": "Подписка активна",
  "freeTrial.success.alreadyActive":
    "У вас уже есть активный доступ. Используйте кнопку ниже.",
  "freeTrial.success.thanks":
    "Спасибо за подписку! Нажмите кнопку, чтобы подключиться.",
  "freeTrial.connect": "Подключить",
  "freeTrial.toHome": "На главную",
  "freeTrial.subscribe": "Подписаться",
  "freeTrial.check": "Проверить",
  "freeTrial.back": "Назад",
  "freeTrial.checking": "Проверяем подписку…",
  "freeTrial.timeoutTitle": "Не удалось подтвердить подписку",
  "freeTrial.timeoutBody":
    "Убедитесь, что вы подписались на канал, и нажмите «Проверить».",
  "freeTrial.error.network": "Сетевая ошибка, повторите попытку.",
  "freeTrial.error.notSubscribed":
    "Подписка на канал не найдена. Подпишитесь и попробуйте снова.",
  "freeTrial.error.createFailed":
    "Не удалось создать подписку. Попробуйте позже.",
  "freeTrial.error.updateFailed":
    "Не удалось обновить подписку. Попробуйте позже.",
  "freeTrial.error.banned": "Аккаунт заблокирован.",

  // buy
  "buy.title": "Тарифы",
  "buy.bonusBalance": "Бонусный баланс:",
  "buy.level.tariff": "Тариф",
  "buy.level.period": "Период",
  "buy.level.subcategory": "Подкатегория",
  "buy.paymentMethod": "Метод оплаты",
  "buy.hint.selectCategory": "Выберите категорию выше",
  "buy.hint.none": "Тарифы не найдены",
  "buy.daysShort": "{count} дн.",
  "buy.payCredits": "Оплатить баллами · {cost}",
  "buy.pay": "Оплатить",
  "buy.loadError": "Не удалось загрузить меню",
  "buy.alert.missingDays": "Тариф не настроен: отсутствует количество дней",
  "buy.alert.invoiceError": "Ошибка создания счёта: {message}",
  "buy.alert.creditsError": "Ошибка оплаты баллами: {message}",

  // buy success
  "buySuccess.paidTitle": "Оплата получена",
  "buySuccess.paidBody":
    "Подписка активирована. Откройте ссылку, чтобы подключиться:",
  "buySuccess.openSub": "Открыть подписку",
  "buySuccess.toHome": "На главную",
  "buySuccess.timeoutTitle":
    "Подтверждение оплаты заняло больше времени, чем ожидалось",
  "buySuccess.timeoutBody":
    "Если деньги уже списаны — подписка появится в течение нескольких минут. Откройте главную и нажмите «Обновить».",
  "buySuccess.waitingTitle": "Ждём подтверждение оплаты…",
  "buySuccess.waitingBody":
    "Это занимает обычно несколько секунд. Не закрывайте окно.",
  "buySuccess.reopenPayment": "Открыть страницу оплаты ещё раз",

  // connect
  "connect.title": "Подключение",
  "connect.backAria": "Назад",
  "connect.subLinkLabel": "Ссылка-подписка",
  "connect.copyLink": "Скопировать ссылку",
  "connect.featured": "Рекомендуем",
  "connect.toast.copied": "Скопировано",
  "connect.toast.copyFailed": "Не удалось скопировать",
  "connect.toast.linkCopied": "Ссылка скопирована",
  "connect.platform.ios": "iOS",
  "connect.platform.android": "Android",
  "connect.platform.windows": "Windows",
  "connect.platform.macos": "macOS",
  "connect.platform.linux": "Linux",
  "connect.platform.appleTV": "Apple TV",
  "connect.platform.androidTV": "Android TV",

  // support
  "support.title": "Поддержка",
  "support.empty": "У вас пока нет обращений.\nНажмите «+», чтобы создать.",
  "support.newAria": "Новое обращение",

  // support create
  "supportCreate.title": "Новое обращение",
  "supportCreate.subjectLabel": "Тема",
  "supportCreate.subjectPlaceholder": "Тема обращения",
  "supportCreate.messageLabel": "Сообщение",
  "supportCreate.messagePlaceholder": "Опишите проблему",
  "supportCreate.error.subject": "Введите тему",
  "supportCreate.error.message": "Опишите проблему",
  "supportCreate.submit": "Отправить",
  "supportCreate.submitting": "Отправляем…",
  "supportCreate.cancel": "Отмена",

  // support ticket
  "supportTicket.back": "Назад",
  "supportTicket.statusLabel": "Статус",
  "supportTicket.createdLabel": "Создан",
  "supportTicket.sender.admin": "Поддержка",
  "supportTicket.sender.you": "Вы",
  "supportTicket.closed":
    "Обращение закрыто. Создайте новое, если нужна помощь.",
  "supportTicket.replyPlaceholder": "Ваше сообщение",
  "supportTicket.photo": "Фото",
  "supportTicket.send": "Отправить",
  "supportTicket.error.maxImages":
    "Можно прикрепить не более {max} изображений",
  "supportTicket.error.fileTooLarge":
    "Файл слишком большой (макс. 5MB): {name}",

  // settings
  "settings.title": "Аккаунт",
  "settings.telegram": "Telegram",
  "settings.email": "Email",
  "settings.bonusBalance": "Бонусный баланс",
  "settings.activatePromo": "Активировать промокод",
  "settings.inviteFriends": "Пригласить друзей",
  "settings.referralRules": "Правила реферальной программы",
  "settings.privacy": "Политика конфиденциальности",
  "settings.agreement": "Пользовательское соглашение",
  "settings.language": "Язык",
  "settings.language.ru": "Русский",
  "settings.language.en": "English",
  "settings.promo.modalTitle": "Активировать промокод",
  "settings.promo.modalBody":
    "Введите промокод — баллы {icon} начислятся на баланс сразу",
  "settings.promo.placeholder": "EXAMPLE123",
  "settings.promo.apply": "Применить",
  "settings.promo.applying": "Применяем…",
  "settings.promo.toastSuccess": "+{grant} на баланс (всего {balance})",
  "settings.promo.errorFallback": "Ошибка",
  "settings.language.toastSaved": "Язык сохранён",
  "settings.language.toastFailed": "Не удалось сохранить язык",
  "settings.linkEmail.title": "Уже есть аккаунт?",
  "settings.linkEmail.body":
    "Войдите по email и паролю, чтобы привязать этот Telegram к существующему аккаунту.",
  "settings.linkEmail.email": "Email",
  "settings.linkEmail.password": "Пароль",
  "settings.linkEmail.submit": "Привязать аккаунт",
  "settings.linkEmail.submitting": "Привязываем…",
  "settings.linkEmail.success": "Аккаунт привязан",
  "settings.linkEmail.errCredentials": "Неверный email или пароль",
  "settings.linkEmail.errConflict":
    "Этот email уже привязан к другому Telegram. Обратитесь в поддержку.",
  "settings.linkEmail.errHasEmail": "К этому Telegram уже привязан email-аккаунт.",
  "settings.linkEmail.errGeneric": "Не удалось привязать аккаунт. Попробуйте снова.",
  "settings.linkEmail.contactSupport": "Написать в поддержку",

  // invite
  "invite.title": "Пригласить друзей",
  "invite.backAria": "Назад",
  "invite.yourCode": "Ваш промокод",
  "invite.copyCode": "Скопировать код",
  "invite.share": "Поделиться",
  "invite.stat.purchased": "Куплено по коду",
  "invite.stat.rewarded": "Начислено вам",
  "invite.howTitle": "Как это работает",
  "invite.howBody":
    "Друг получает {creditGrant} при активации кода. За каждые 30 дней покупок по вашему коду вы получаете {per30} — всего до {cap}.",
  "invite.shareText":
    "Подключайся к VPN и получи {creditGrant} по моему коду!",
  "invite.toast.copied": "Промокод скопирован",
  "invite.toast.copyFailed": "Не удалось скопировать",
  "invite.daysShort": "{count} дн.",

  // referral rules
  "referralRules.title": "Правила реферальной программы",
  "referralRules.titleLoading": "Правила программы",
  "referralRules.s1.title": "Реферальные промокоды",
  "referralRules.s1.i1":
    "У каждого пользователя есть личный промокод — поделитесь им с друзьями.",
  "referralRules.s1.i2": "Друг получает {creditGrant} при активации кода.",
  "referralRules.s1.i3":
    "Реферальный промокод доступен только новым пользователям — у кого ещё не было покупок.",
  "referralRules.s1.i4":
    "Активировать реферальный промокод можно только один раз.",
  "referralRules.s2.title": "Бонусы за приглашения",
  "referralRules.s2.i1":
    "За каждые 30 дней покупок по вашему коду вы получаете {per30}.",
  "referralRules.s2.i2": "Всего можно получить до {cap}.",
  "referralRules.s3.title": "Обычные промокоды",
  "referralRules.s3.i1": "Доступны всем пользователям.",
  "referralRules.s3.i2":
    "Каждый конкретный промокод можно использовать только один раз.",
  "referralRules.s3.i3":
    "Одновременно может быть активен только один промокод — используйте его при оплате перед активацией следующего.",

  // welcome
  "welcome.title": "Добро пожаловать!",
  "welcome.body":
    "Чтобы пользоваться приложением, сначала запустите Telegram-бота и зарегистрируйтесь.",
  "welcome.cta": "Запустить бота",

  // legal layout
  "legal.back": "Назад",
  "legal.supportFallback": "поддержка",
  "legal.brandFallback": "VPN",

  // policy
  "legal.policy.title": "Политика конфиденциальности",
  "legal.policy.s1.title": "1. Собираемые данные",
  "legal.policy.s1.p1": "1.1. Обязательные данные:",
  "legal.policy.s1.i1": "Telegram User ID",
  "legal.policy.s1.i2": "Имя пользователя Telegram",
  "legal.policy.s1.i3": "Данные оплаты (через платёжные агрегаторы)",
  "legal.policy.s1.p2": "1.2. Технические данные:",
  "legal.policy.s1.i4": "Время подключения",
  "legal.policy.s1.i5": "Тип устройства (без IMEI / серийных номеров)",
  "legal.policy.s1.i6": "Объём трафика (без анализа содержимого)",
  "legal.policy.s2.title": "2. Запрет на сбор",
  "legal.policy.s2.p1": "2.1. Мы никогда не сохраняем:",
  "legal.policy.s2.i1": "Историю посещённых сайтов",
  "legal.policy.s2.i2": "IP-адреса пользователей",
  "legal.policy.s2.i3": "Передаваемый контент (файлы, сообщения)",
  "legal.policy.s3.title": "3. Использование данных",
  "legal.policy.s3.p1": "3.1. Данные используются исключительно для:",
  "legal.policy.s3.i1": "Активации доступа к VPN",
  "legal.policy.s3.i2": "Оказания технической поддержки",
  "legal.policy.s3.i3": "Оповещений о новых тарифах и изменениях в сервисе",
  "legal.policy.s4.title": "4. Защита данных",
  "legal.policy.s4.p1":
    "4.1. Все данные хранятся на зашифрованных серверах в юрисдикциях, не требующих хранения логов (Швейцария, Румыния).",
  "legal.policy.s4.p2":
    "4.2. Ключи доступа к VPN генерируются автоматически и удаляются при отмене подписки.",
  "legal.policy.s5.title": "5. Передача третьим лицам",
  "legal.policy.s5.p1": "5.1. Данные передаются только в следующих случаях:",
  "legal.policy.s5.i1": "Платёжным системам для обработки транзакций",
  "legal.policy.s5.i2": "По официальному запросу уполномоченных органов РФ",
  "legal.policy.s6.title": "6. Срок хранения",
  "legal.policy.s6.p1": "6.1. Ваши данные удаляются:",
  "legal.policy.s6.i1": "Через 30 дней после прекращения подписки",
  "legal.policy.s6.i2": "По вашему запросу через службу поддержки",
  "legal.policy.s7.title": "7. Права пользователя",
  "legal.policy.s7.p1": "Вы имеете право запросить:",
  "legal.policy.s7.i1": "Доступ к вашим данным",
  "legal.policy.s7.i2": "Исправление неточной информации",
  "legal.policy.s7.i3": "Удаление аккаунта и всех связанных данных",
  "legal.policy.s7.p2": "Для реализации этих прав обратитесь в поддержку:",
  "legal.policy.footer":
    "Используя сервис {brand}, вы подтверждаете согласие с настоящей политикой.",

  // agreement
  "legal.agreement.title": "Пользовательское соглашение",
  "legal.agreement.s1.title": "1. Предмет соглашения",
  "legal.agreement.s1.p1":
    "1.1. Сервис {brand} предоставляет доступ к VPN-серверам через Telegram-бота для шифрования интернет-трафика.",
  "legal.agreement.s1.p2":
    "1.2. Услуги доступны только совершеннолетним пользователям. Использование бота означает акцепт оферты.",
  "legal.agreement.s2.title": "2. Условия использования",
  "legal.agreement.s2.p1": "2.1. Пользователь обязуется:",
  "legal.agreement.s2.i1":
    "Не нарушать законы РФ (включая обход блокировок запрещённых ресурсов: экстремистские материалы, наркотики и т. д.);",
  "legal.agreement.s2.i2": "Не распространять вредоносное ПО;",
  "legal.agreement.s2.i3":
    "Не использовать сервис для DDoS-атак, спама или взлома.",
  "legal.agreement.s2.p2": "2.2. Запрещено:",
  "legal.agreement.s2.i4": "Передавать аккаунт третьим лицам;",
  "legal.agreement.s2.i5": "Мешать работе сервиса.",
  "legal.agreement.s3.title": "3. Оплата и возврат",
  "legal.agreement.s3.p1":
    "3.1. Оплата тарифов осуществляется через Telegram-бота (карты, Qiwi, криптовалюты).",
  "legal.agreement.s3.p2":
    "3.2. Возврат средств возможен только при технической невозможности предоставить услугу.",
  "legal.agreement.s4.title": "4. Ответственность",
  "legal.agreement.s4.p1": "4.1. Сервис не гарантирует 100% доступность VPN.",
  "legal.agreement.s4.p2": "4.2. Администрация не несёт ответственности за:",
  "legal.agreement.s4.i1": "Нелегальные действия пользователей;",
  "legal.agreement.s4.i2": "Ущерб из-за сбоев VPN;",
  "legal.agreement.s4.i3": "Блокировку доступа к ресурсам.",
  "legal.agreement.s5.title": "5. Расторжение",
  "legal.agreement.s5.p1":
    "5.1. Администрация вправе заблокировать аккаунт при нарушении п. 2 без возврата средств.",
  "legal.agreement.s5.p2":
    "5.2. Пользователь может отказаться от услуг, прекратив оплату.",
  "legal.agreement.s6.title": "6. Контакты",
  "legal.agreement.s6.p1": "Поддержка:",
  "legal.agreement.callout":
    "Используя сервис {brand}, вы подтверждаете, что ознакомились и согласны с условиями данного соглашения.",
};
