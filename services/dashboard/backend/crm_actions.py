"""CRM action types and per-user execution pipeline."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from common_db.models import User
from common_db.models.credit_ledger import SOURCE_CRM
from common_db.repo import balance as _repo_balance
from common_db.repo import promos as _repo_promos
from common_db.repo import system as _repo_system
from remnawave_client.perks import apply_crm_bonus_days, apply_crm_bonus_traffic

from .crm_model_adapter import (
    ACTION_ATTACH_BUTTON,
    ACTION_CREDIT_BALANCE,
    ACTION_RW_BONUS_DAYS,
    ACTION_RW_BONUS_TRAFFIC,
    ACTION_RW_RESET_TRAFFIC,
    ACTION_RW_SET_STATUS,
    ACTION_SEND_MESSAGE,
    normalize_actions,
)
from .crm_variables import build_message_context, render_crm_message
from .database.session import async_session
from .telegram import tg_bot_deeplink, tg_bot_open_url, tg_send, tg_share_url

logger = logging.getLogger(__name__)

BUTTON_OPEN_BOT = "open_bot"
BUTTON_INVITE_FRIENDS = "invite_friends"

ACTION_CATALOG: list[dict[str, Any]] = [
    {
        "type": ACTION_SEND_MESSAGE,
        "label": "Send message",
        "category": "telegram",
        "fields": [{"name": "text", "label": "Text (HTML)", "type": "textarea"}],
    },
    {
        "type": ACTION_ATTACH_BUTTON,
        "label": "Attach button",
        "category": "telegram",
        "fields": [
            {
                "name": "button_type",
                "label": "Button type",
                "type": "select",
                "options": [
                    {"value": BUTTON_OPEN_BOT, "label": "Open bot"},
                    {"value": BUTTON_INVITE_FRIENDS, "label": "Invite friends"},
                ],
                "default": BUTTON_OPEN_BOT,
            }
        ],
    },
    {
        "type": ACTION_CREDIT_BALANCE,
        "label": "Grant credits",
        "category": "wallet",
        "fields": [{"name": "days", "label": "Credits (days)", "type": "int", "min": 1, "max": 365}],
    },
    {
        "type": ACTION_RW_BONUS_DAYS,
        "label": "Add days",
        "category": "remnawave",
        "fields": [{"name": "days", "label": "Days", "type": "int", "min": 1, "max": 365}],
    },
    {
        "type": ACTION_RW_BONUS_TRAFFIC,
        "label": "Add traffic (GB)",
        "category": "remnawave",
        "fields": [{"name": "gb", "label": "GB", "type": "int", "min": 1, "max": 1000}],
    },
    {
        "type": ACTION_RW_RESET_TRAFFIC,
        "label": "Reset traffic",
        "category": "remnawave",
        "fields": [],
    },
    {
        "type": ACTION_RW_SET_STATUS,
        "label": "Change status",
        "category": "remnawave",
        "available": False,
        "fields": [
            {
                "name": "status",
                "label": "Status",
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


async def _build_invite_friends_markup(
    session,
    *,
    tg_id: int,
    bot_username: str,
) -> dict | None:
    """Build share-sheet URL keyboard; creates referral code if missing."""
    code = await _repo_promos.get_or_create_referral_code(session, tg_id)
    grant = await _repo_system.get_default_credit_grant(session)
    deeplink = tg_bot_deeplink(bot_username, code)
    invite_text = f"Подключайся к VPN и получи {grant} 🪙 по моему коду!"
    share = tg_share_url(deeplink, invite_text)
    return {
        "inline_keyboard": [[{"text": "Пригласить друзей", "url": share}]]
    }


async def execute_user_actions(
    rw_client,
    db_user: User,
    crm_user: dict | None,
    actions: list[dict],
    *,
    bot_username: str | None = None,
    event_id: int | None = None,
    on_message_sent=None,
    session=None,
    message_ctx: dict[str, str] | None = None,
) -> UserActionResult:
    """Run enabled actions for one user. RW actions first, then Telegram."""
    result = UserActionResult()
    ordered = normalize_actions(list(actions))
    enabled = [a for a in ordered if a.get("enabled", True)]

    message_text: str | None = None
    attach_button = False
    button_type = BUTTON_OPEN_BOT

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
        elif atype == ACTION_CREDIT_BALANCE:
            credits = int(act.get("days") or 0)
            if credits > 0:
                try:
                    async with async_session() as bal_session:
                        await _repo_balance.credit(
                            bal_session,
                            db_user.id,
                            credits,
                            SOURCE_CRM,
                            reference=f"crm:{event_id or 'batch'}",
                        )
                        await bal_session.commit()
                    result.perks_applied = True
                except Exception as exc:
                    result.perks_failed = True
                    result.errors.append(f"credit_balance: {exc}")
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
            button_type = act.get("button_type") or BUTTON_OPEN_BOT

    if message_text and not result.message_skipped:
        ctx = message_ctx or build_message_context(
            username=db_user.username, crm_user=crm_user
        )
        personalized = render_crm_message(message_text, ctx)
        reply_markup = None
        if attach_button:
            if button_type == BUTTON_OPEN_BOT and bot_username:
                reply_markup = {
                    "inline_keyboard": [[
                        {"text": "Открыть бота", "url": tg_bot_open_url(bot_username)}
                    ]]
                }
            elif button_type == BUTTON_INVITE_FRIENDS:
                if not bot_username:
                    result.errors.append("invite_friends: bot username unavailable")
                elif not db_user.tg_id:
                    result.errors.append("invite_friends: no tg_id")
                elif session is None:
                    result.errors.append("invite_friends: session required")
                else:
                    try:
                        reply_markup = await _build_invite_friends_markup(
                            session,
                            tg_id=db_user.tg_id,
                            bot_username=bot_username,
                        )
                    except Exception as exc:
                        result.errors.append(f"invite_friends: {exc}")
                        logger.exception(
                            "invite_friends markup failed tg_id=%s", db_user.tg_id
                        )
        if await tg_send(db_user.tg_id, personalized, reply_markup):
            result.message_sent = True
            if on_message_sent:
                await on_message_sent()
        else:
            result.message_failed = True
            result.errors.append("telegram send failed")

    return result
