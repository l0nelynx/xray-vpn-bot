"""CRM action types and per-user execution pipeline."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from common_db.models import User
from remnawave_client.perks import apply_crm_bonus_days, apply_crm_bonus_traffic

from .crm_model_adapter import (
    ACTION_ATTACH_BUTTON,
    ACTION_RW_BONUS_DAYS,
    ACTION_RW_BONUS_TRAFFIC,
    ACTION_RW_RESET_TRAFFIC,
    ACTION_RW_SET_STATUS,
    ACTION_SEND_MESSAGE,
    normalize_actions,
)
from .crm_variables import build_message_context, render_crm_message
from .telegram import tg_bot_open_url, tg_send

logger = logging.getLogger(__name__)

ACTION_CATALOG: list[dict[str, Any]] = [
    {
        "type": ACTION_SEND_MESSAGE,
        "label": "Отправить сообщение",
        "category": "telegram",
        "fields": [{"name": "text", "label": "Текст (HTML)", "type": "textarea"}],
    },
    {
        "type": ACTION_ATTACH_BUTTON,
        "label": "Прикрепить кнопку",
        "category": "telegram",
        "fields": [
            {
                "name": "button_type",
                "label": "Тип кнопки",
                "type": "select",
                "options": [{"value": "open_bot", "label": "Открыть бота"}],
                "default": "open_bot",
            }
        ],
    },
    {
        "type": ACTION_RW_BONUS_DAYS,
        "label": "Добавить дней",
        "category": "remnawave",
        "fields": [{"name": "days", "label": "Дней", "type": "int", "min": 1, "max": 365}],
    },
    {
        "type": ACTION_RW_BONUS_TRAFFIC,
        "label": "Добавить трафика (ГБ)",
        "category": "remnawave",
        "fields": [{"name": "gb", "label": "ГБ", "type": "int", "min": 1, "max": 1000}],
    },
    {
        "type": ACTION_RW_RESET_TRAFFIC,
        "label": "Сбросить трафик",
        "category": "remnawave",
        "fields": [],
    },
    {
        "type": ACTION_RW_SET_STATUS,
        "label": "Изменить статус",
        "category": "remnawave",
        "available": False,
        "fields": [
            {
                "name": "status",
                "label": "Статус",
                "type": "select",
                "options": [
                    {"value": "active", "label": "active"},
                    {"value": "limited", "label": "limited"},
                ],
            }
        ],
    },
]


def action_types_catalog() -> list[dict[str, Any]]:
    return list(ACTION_CATALOG)


@dataclass
class UserActionResult:
    perks_applied: bool = False
    perks_failed: bool = False
    message_sent: bool = False
    message_failed: bool = False
    message_skipped: bool = True
    errors: list[str] = field(default_factory=list)


async def execute_user_actions(
    rw_client,
    db_user: User,
    crm_user: dict | None,
    actions: list[dict],
    *,
    bot_username: str | None = None,
    event_id: int | None = None,
    on_message_sent=None,
) -> UserActionResult:
    """Run enabled actions for one user. RW actions first, then Telegram."""
    result = UserActionResult()
    ordered = normalize_actions(list(actions))
    enabled = [a for a in ordered if a.get("enabled", True)]

    message_text: str | None = None
    attach_button = False
    button_type = "open_bot"

    username = db_user.username or f"user_{db_user.tg_id}"
    has_rw = any(
        a.get("type") in {
            ACTION_RW_BONUS_DAYS,
            ACTION_RW_BONUS_TRAFFIC,
            ACTION_RW_RESET_TRAFFIC,
            ACTION_RW_SET_STATUS,
        }
        for a in enabled
    )

    if has_rw and not db_user.vless_uuid:
        result.perks_failed = True
        result.errors.append("no vless_uuid for remnawave actions")
    elif has_rw and not crm_user:
        result.perks_failed = True
        result.errors.append("remnawave user not found")

    for act in enabled:
        atype = act.get("type")
        if atype == ACTION_RW_BONUS_DAYS:
            days = int(act.get("days") or 0)
            if days > 0 and db_user.vless_uuid and crm_user:
                ok = await apply_crm_bonus_days(
                    user_uuid=db_user.vless_uuid,
                    username=username,
                    bonus_days=days,
                    crm_user=crm_user,
                    client=rw_client,
                )
                if ok:
                    result.perks_applied = True
                else:
                    result.perks_failed = True
                    result.errors.append("bonus_days failed")
        elif atype == ACTION_RW_BONUS_TRAFFIC:
            gb = int(act.get("gb") or 0)
            if gb > 0 and db_user.vless_uuid and crm_user:
                ok = await apply_crm_bonus_traffic(
                    user_uuid=db_user.vless_uuid,
                    username=username,
                    bonus_gb=gb,
                    crm_user=crm_user,
                    client=rw_client,
                )
                if ok:
                    result.perks_applied = True
                else:
                    result.perks_failed = True
                    result.errors.append("bonus_traffic failed")
        elif atype == ACTION_RW_RESET_TRAFFIC:
            if db_user.vless_uuid:
                try:
                    ok = await rw_client.reset_user_traffic(db_user.vless_uuid)
                    if ok:
                        result.perks_applied = True
                    else:
                        result.perks_failed = True
                        result.errors.append("reset_traffic failed")
                except Exception as exc:
                    result.perks_failed = True
                    result.errors.append(f"reset_traffic: {exc}")
        elif atype == ACTION_RW_SET_STATUS:
            if act.get("available", True) is False:
                continue
            result.errors.append("rw_set_status not implemented")
            result.perks_failed = True
        elif atype == ACTION_SEND_MESSAGE:
            text = (act.get("text") or "").strip()
            if text:
                message_text = text
                result.message_skipped = False
        elif atype == ACTION_ATTACH_BUTTON:
            attach_button = True
            button_type = act.get("button_type") or "open_bot"

    if message_text and not result.message_skipped:
        ctx = build_message_context(username=db_user.username, crm_user=crm_user)
        personalized = render_crm_message(message_text, ctx)
        reply_markup = None
        if attach_button and button_type == "open_bot" and bot_username:
            reply_markup = {
                "inline_keyboard": [[
                    {"text": "Открыть бота", "url": tg_bot_open_url(bot_username)}
                ]]
            }
        if await tg_send(db_user.tg_id, personalized, reply_markup):
            result.message_sent = True
            if on_message_sent:
                await on_message_sent()
        else:
            result.message_failed = True
            result.errors.append("telegram send failed")

    return result
