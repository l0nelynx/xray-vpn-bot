"""Static CRM message templates per segment."""

from __future__ import annotations

from remnawave_client.segmentation import (
    SEGMENT_ALL_USERS,
    SEGMENT_DEVICE_LIMIT,
    SEGMENT_EXPIRED,
    SEGMENT_EXPIRING_SOON,
    SEGMENT_LIMITED,
    SEGMENT_NEVER_CONNECTED,
    SEGMENT_TORRENT,
    SEGMENT_TRAFFIC_LOW,
    SEGMENT_UNPAID_INVOICE,
)

_TEMPLATES: list[dict] = [
    {
        "id": "all_users_announce",
        "segment_id": SEGMENT_ALL_USERS,
        "title": "Общее объявление",
        "message_text": (
            "<b>Важное сообщение</b>\n\n"
            "Привет, {{username}}! У нас есть новости для всех пользователей."
        ),
        "suggested_bonus_days": None,
        "suggested_bonus_traffic_gb": None,
        "attach_button": True,
    },
    {
        "id": "never_connected_nudge",
        "segment_id": SEGMENT_NEVER_CONNECTED,
        "title": "Напоминание подключиться",
        "message_text": (
            "<b>Вы ещё не подключались</b>\n\n"
            "Привет, {{username}}! Подписка активна, но подключений не было. "
            "Откройте бота и получите ссылку для настройки VPN."
        ),
        "suggested_bonus_days": None,
        "suggested_bonus_traffic_gb": None,
        "attach_button": True,
    },
    {
        "id": "never_connected_bonus",
        "segment_id": SEGMENT_NEVER_CONNECTED,
        "title": "Бонус за первое подключение",
        "message_text": (
            "<b>Бонус за подключение</b>\n\n"
            "{{username}}, подключитесь к VPN — мы начислили вам дополнительные дни."
        ),
        "suggested_bonus_days": 3,
        "suggested_bonus_traffic_gb": None,
        "attach_button": True,
    },
    {
        "id": "expired_renew",
        "segment_id": SEGMENT_EXPIRED,
        "title": "Подписка истекла",
        "message_text": (
            "<b>Подписка истекла</b>\n\n"
            "{{username}}, ваша подписка больше не активна. "
            "Продлите доступ в боте, чтобы снова пользоваться VPN."
        ),
        "suggested_bonus_days": None,
        "suggested_bonus_traffic_gb": None,
        "attach_button": True,
    },
    {
        "id": "limited_upgrade",
        "segment_id": SEGMENT_LIMITED,
        "title": "LIMITED — предложение PRO",
        "message_text": (
            "<b>Трафик FREE-подписки исчерпан</b>\n\n"
            "Привет, {{username}}! Статус: <code>{{status}}</code>.\n"
            "Оформите PRO-подписку для безлимитного доступа или дождитесь обновления лимита."
        ),
        "suggested_bonus_days": None,
        "suggested_bonus_traffic_gb": None,
        "attach_button": True,
    },
    {
        "id": "limited_bonus_traffic",
        "segment_id": SEGMENT_LIMITED,
        "title": "LIMITED — бонус трафика",
        "message_text": (
            "<b>Дополнительный трафик</b>\n\n"
            "{{username}}, мы начислили вам бонусный трафик. "
            "Остаток: {{traffic_left}}."
        ),
        "suggested_bonus_days": None,
        "suggested_bonus_traffic_gb": 5,
        "attach_button": True,
    },
    {
        "id": "traffic_low_warning",
        "segment_id": SEGMENT_TRAFFIC_LOW,
        "title": "Трафик заканчивается",
        "message_text": (
            "<b>Трафик почти исчерпан</b>\n\n"
            "{{username}}, использовано {{traffic_percent}}% лимита. "
            "Осталось: {{traffic_left}}."
        ),
        "suggested_bonus_days": None,
        "suggested_bonus_traffic_gb": None,
        "attach_button": True,
    },
    {
        "id": "traffic_low_bonus",
        "segment_id": SEGMENT_TRAFFIC_LOW,
        "title": "Трафик — бонус ГБ",
        "message_text": (
            "<b>Бонус трафика</b>\n\n"
            "{{username}}, начислили дополнительный трафик. Текущий остаток: {{traffic_left}}."
        ),
        "suggested_bonus_days": None,
        "suggested_bonus_traffic_gb": 3,
        "attach_button": True,
    },
    {
        "id": "expiring_soon_renew",
        "segment_id": SEGMENT_EXPIRING_SOON,
        "title": "Скоро истечёт",
        "message_text": (
            "<b>Подписка скоро истечёт</b>\n\n"
            "{{username}}, осталось {{days_left}} дн. Продлите подписку заранее."
        ),
        "suggested_bonus_days": None,
        "suggested_bonus_traffic_gb": None,
        "attach_button": True,
    },
    {
        "id": "expiring_soon_bonus",
        "segment_id": SEGMENT_EXPIRING_SOON,
        "title": "Скоро истечёт — бонус дней",
        "message_text": (
            "<b>Бонусные дни</b>\n\n"
            "{{username}}, начислили +дни к подписке. Осталось {{days_left}} дн."
        ),
        "suggested_bonus_days": 3,
        "suggested_bonus_traffic_gb": None,
        "attach_button": True,
    },
    {
        "id": "unpaid_invoice_remind",
        "segment_id": SEGMENT_UNPAID_INVOICE,
        "title": "Неоплаченный инвойс",
        "message_text": (
            "<b>Ожидается оплата</b>\n\n"
            "{{username}}, у вас есть неоплаченный заказ. Завершите оплату в боте."
        ),
        "suggested_bonus_days": None,
        "suggested_bonus_traffic_gb": None,
        "attach_button": True,
    },
    {
        "id": "torrent_warning",
        "segment_id": SEGMENT_TORRENT,
        "title": "Torrent — предупреждение",
        "message_text": (
            "<b>Torrent-трафик</b>\n\n"
            "{{username}}, зафиксирован torrent-трафик. "
            "Использование torrent может привести к ограничению доступа."
        ),
        "suggested_bonus_days": None,
        "suggested_bonus_traffic_gb": None,
        "attach_button": True,
    },
    {
        "id": "device_limit_notice",
        "segment_id": SEGMENT_DEVICE_LIMIT,
        "title": "Лимит устройств",
        "message_text": (
            "<b>Лимит устройств</b>\n\n"
            "{{username}}, подключено устройств: {{hwid_devices}}. "
            "Удалите лишние устройства в боте или оформите PRO."
        ),
        "suggested_bonus_days": None,
        "suggested_bonus_traffic_gb": None,
        "attach_button": True,
    },
]

_BY_ID = {t["id"]: t for t in _TEMPLATES}


def list_templates(*, segment_id: str | None = None) -> list[dict]:
    if segment_id:
        return [t for t in _TEMPLATES if t["segment_id"] == segment_id]
    return list(_TEMPLATES)


def get_template(template_id: str) -> dict | None:
    return _BY_ID.get(template_id)
